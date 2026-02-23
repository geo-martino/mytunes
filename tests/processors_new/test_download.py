import itertools
import math
from copy import copy
from random import sample, randrange
from unittest import mock
from urllib.parse import unquote

import pytest
from faker import Faker

from musify import MODULE_ROOT
from musify.models.collection.playlist import Playlist
from musify.models.item.album import Album
from musify.models.item.artist import Artist
from musify.models.item.track import Track
from musify.processors_new.download import ItemDownloadHelper
from tests.conftest import LogCapturer
from tests.libraries.remote.core.processors.utils import patch_input
from tests.models.testers import MusifyModelTester


class TestItemDownloadHelper(MusifyModelTester):

    @pytest.fixture
    def model(self, faker: Faker) -> ItemDownloadHelper:
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
            fields=["name", "artists"],
            interval=faker.random_int(1, 5),
        )

    def test_validate_urls(self):
        with pytest.raises(ValueError, match="String should match pattern"):
            ItemDownloadHelper(urls=[
                "https://example.com/search?q={}&type=t", "https://example.com/search?q={}&limit={}"
            ])

        with pytest.raises(ValueError, match="Input should be a valid URL"):
            ItemDownloadHelper(urls=[
                "https://example.com/search?q={}&type=t", "not_a_valid_url_with_placeholder_{}"
            ])

    def test_url_counts(self, model: ItemDownloadHelper, playlists: list[Playlist]):
        track_total = sum(pl.track_total for pl in playlists)
        with (
            mock.patch(f"{MODULE_ROOT}.processors_new.download.webopen") as mock_webopen,
            mock.patch.object(ItemDownloadHelper, "_pause") as mock_pause,
        ):
            model.open_sites_for_collections(playlists)

            assert mock_pause.call_count == math.ceil(track_total / model.interval)
            assert mock_webopen.call_count == track_total * len(model.urls)

    def test_url_formats(self, model: ItemDownloadHelper, tracks: list[Track], artists: list[Artist], faker: Faker):
        for track in tracks:
            track.artists = sample(artists, k=faker.random_int(0, 3))

        urls: list[str] = []
        with (
            mock.patch(f"{MODULE_ROOT}.processors_new.download.webopen", new=urls.append),
            mock.patch.object(ItemDownloadHelper, "_pause"),
        ):
            model.open_sites(tracks)

        urls_batched = itertools.batched(urls, len(model.urls))
        for track in tracks:
            for url in next(urls_batched):
                url = unquote(url)
                assert track.name in url
                if len(track.artists) > 0:
                    assert track.artists[0].name in url

                # only ever takes the first field when the singular name of a field is given
                # and many values are available for that field
                # e.g. only ever takes the first artist when multiple artists are present
                # and the requested field is just 'artist' not 'artists'
                if len(track.artists) > 1:
                    assert track.artist not in url

    def test_pause_1(self, model: ItemDownloadHelper, tracks: list[Track], log_capturer: LogCapturer):
        total = len(tracks)
        pages_total = math.ceil(total / model.interval)

        urls = []
        with (
            mock.patch(f"{MODULE_ROOT}.processors_new.download.webopen", new=urls.append),
            patch_input(["r", "", "name artists", "r", "bad_tag", "r", "name bad_tag", ""] + [""] * total),
            log_capturer(loggers=model.logger),
        ):
            model.open_sites(tracks)

        # 5 extra for 3*r input + 2*<Fields> input
        assert len(urls) == (total + 5 * model.interval) * len(model.urls)

        assert log_capturer.text.count("Enter one of the following") == pages_total
        assert log_capturer.text.count("Some fields were not recognised") == 1
        assert log_capturer.text.count("Unrecognised input") == 1

    def test_pause_2(
            self,
            model: ItemDownloadHelper,
            tracks: list[Track],
            artists: list[Artist],
            albums: list[Album],
            faker: Faker,
            log_capturer: LogCapturer
    ):
        for track in tracks:
            track.artists = faker.random_elements(artists, length=faker.random_int(1, 3))
            track.album = faker.random_element(albums)

        # force a few poison apples
        test_tracks = list(map(copy, tracks[:10]))
        for item in sample(test_tracks, k=3):
            item.artist = None
            item.album = None

        model.fields = ["artists", "album"]
        model.interval = len(test_tracks)

        urls = []
        with (
            mock.patch(f"{MODULE_ROOT}.processors_new.download.webopen", new=urls.append),
            patch_input(["h", "artists", "h", "n name", "h", "", "h", "h"]),
            log_capturer(loggers=model.logger),
        ):
            model.open_sites(test_tracks)

        # Extra:
        # 1*<Fields>*tracks input - 2*3 for poison apples input failing + 3*n<Fields> for poison apples input repeat
        assert len(urls) == (2 * len(test_tracks) - 3) * len(model.urls)

        assert log_capturer.text.count("Enter one of the following") == 4
        assert log_capturer.text.count("Could not open sites for 3 tracks") == 4
        assert "Some fields were not recognised" not in log_capturer.text
        assert "Unrecognised input" not in log_capturer.text
