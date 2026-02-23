import itertools
from copy import copy
from random import sample, randrange
from urllib.parse import unquote

import pytest
from pytest_mock import MockerFixture

from musify import MODULE_ROOT
from musify.field import Fields
from musify.libraries.collection import BasicCollection
from musify.libraries.local.track import LocalTrack
from musify.processors.download import ItemDownloadHelper
from tests.conftest import LogCapturer
from tests.libraries.local.track.utils import random_tracks
from tests.libraries.remote.core.processors.utils import patch_input
from tests.testers import PrettyPrinterTester
from tests.utils import random_str


class TestItemDownloadHelper(PrettyPrinterTester):
    """Run generic tests for :py:class:`RemoteItemDownloadHelper` implementations."""

    @pytest.fixture
    def obj(self, download_helper: ItemDownloadHelper) -> ItemDownloadHelper:
        return download_helper

    @pytest.fixture
    def download_helper(self) -> ItemDownloadHelper:
        """Yields a valid :py:class:`RemoteItemDownloadHelper` for the current remote source as a pytest.fixture."""
        # noinspection SpellCheckingInspection
        sites = [
            "https://bandcamp.com/search?q={}&item_type=t",
            "https://uk.7digital.com/search?q={}&f=9%2C2",
            "https://www.junodownload.com/search/?q%5Ball%5D%5B%5D={}&solrorder=relevancy",
            "https://www.jamendo.com/search?q={}",
            "https://www.amazon.com/s?k={}&i=digital-music",
            "https://www.google.com/search?q={}%20mp3",
        ]
        return ItemDownloadHelper(
            urls=sample(sites, k=randrange(2, len(sites))),
            fields=[Fields.TITLE, Fields.ARTIST],
            interval=1,
        )

    @pytest.fixture
    def collections(self) -> list[BasicCollection[LocalTrack]]:
        """Yields many valid :py:class:`BasicCollection` of :py:class:`RemoteItem` as a pytest.fixture."""
        collections = [BasicCollection(name=random_str(30, 50), items=random_tracks()) for _ in range(randrange(3, 10))]
        assert any(len(track.artists) > 1 for coll in collections for track in coll)
        return collections

    @staticmethod
    def test_valid_setup(download_helper: ItemDownloadHelper, collections: list[BasicCollection]):
        assert len(download_helper.urls) > 1
        assert Fields.ALL in download_helper.fields or len(download_helper.fields) >= 2

        assert sum(map(len, collections)) > 3

    @staticmethod
    @pytest.mark.slow
    def test_opened_urls(
            download_helper: ItemDownloadHelper,
            collections: list[BasicCollection[LocalTrack]],
            mocker: MockerFixture,
    ):
        urls = []
        mocker.patch(f"{MODULE_ROOT}.processors.download.webopen", new=urls.append)

        patch_input(values=[""] * sum(map(len, collections)), mocker=mocker)

        download_helper.open_sites(collections)
        mocker.stopall()

        assert len(urls) == sum(map(len, collections)) * len(download_helper.urls)

        urls_batched = itertools.batched(urls, len(download_helper.urls))
        for collection in collections:
            for track in collection:
                for url in next(urls_batched):
                    url = unquote(url)
                    assert track.title in url
                    assert track.artists[0] in url

                    # only ever takes the first field when the singular name of a field is given
                    # and many values are available for that field
                    # e.g. only ever takes the first artist when multiple artists are present
                    # and the requested field is just 'artist' not 'artists'
                    if len(track.artists) > 1:
                        assert track.artist not in url

    @staticmethod
    def test_pause_1(
            download_helper: ItemDownloadHelper,
            collections: list[BasicCollection],
            mocker: MockerFixture,
            log_capturer: LogCapturer,
    ):
        def log_urls(url) -> None:
            """Log the opened URLs"""
            nonlocal urls
            urls.append(url)

        urls = []
        mocker.patch(f"{MODULE_ROOT}.processors.download.webopen", new=log_urls)

        total = sum(map(len, collections))
        pages_total = (total // download_helper.interval) + (total % download_helper.interval > 0)
        patch_input(values=["r", "", "title artist", "r", "title bad_tag", ""] + [""] * total, mocker=mocker)

        with log_capturer(loggers=download_helper.logger):
            download_helper.open_sites(collections)
        mocker.stopall()

        # 3 extra for 2*r input + 1*<Fields> input
        assert len(urls) == (total + 3) * len(download_helper.urls)

        assert log_capturer.text.count("Enter one of the following") == pages_total
        assert log_capturer.text.count("Some fields were not recognised") == 1

    @staticmethod
    def test_pause_2(
            download_helper: ItemDownloadHelper,
            collections: list[BasicCollection[LocalTrack]],
            mocker: MockerFixture,
            log_capturer: LogCapturer,
    ):
        def log_urls(url) -> None:
            """Log the opened URLs"""
            nonlocal urls
            urls.append(url)

        urls = []
        mocker.patch(f"{MODULE_ROOT}.processors.download.webopen", new=log_urls)

        # force a few poison apples
        test_items = [copy(item) for coll in collections for item in coll][:10]
        for item in sample(test_items, k=3):
            item.artist = None
            item.album = None

        download_helper.fields = [Fields.ARTIST, Fields.ALBUM]
        download_helper.interval = len(test_items)

        patch_input(values=["h", "artist", "h", "n title", "h", "", "h", "h"], mocker=mocker)

        with log_capturer(loggers=download_helper.logger):
            download_helper.open_sites(BasicCollection(name="test", items=test_items))
        mocker.stopall()

        # 3 extra for 2*r input + 1*<Fields> input
        assert len(urls) == (2 * len(test_items) - 3) * len(download_helper.urls)

        assert log_capturer.text.count("Enter one of the following") == 4
        assert "Some fields were not recognised" not in log_capturer.text
