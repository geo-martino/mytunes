import itertools
import math
from collections.abc import Generator
from copy import copy
from unittest.mock import patch, Mock
from urllib.parse import unquote

import pytest
from faker import Faker
from pydantic import ValidationError

from musify import MODULE_ROOT
from musify.models.collection.playlist import Playlist
from musify.models.item.album import Album
from musify.models.item.artist import Artist
from musify.models.item.track import Track
from musify.processors.clean.string import NameCleaner
from musify.processors.download.download import ItemDownloadHelper
from tests.conftest import LogCapturer
from tests.libraries.remote.core.processors.utils import patch_input
from tests.models.testers import BaseModelTester


class TestItemDownloadHelper(BaseModelTester):

    @pytest.fixture
    def model(self, faker: Faker) -> ItemDownloadHelper:
        # noinspection SpellCheckingInspection
        sites = [
            "https://bandcamp.com/search?q={}&item_type=t",
            "https://uk.7digital.com/search?q={}&f=9%2C2",
            "https://www.junodownload.com/search/?q%5Ball%5D%5B%5D={}&solrorder=relevancy",
            "https://www.jamendo.com/search?q={}",
            "https://www.amazon.com/s?length={}&i=digital-music",
            "https://www.google.com/search?q={}%20mp3",
        ]
        return ItemDownloadHelper(
            urls=faker.random_elements(sites, length=faker.random_int(2, len(sites)), unique=True),
            fields=["name", "artists"],
            interval=faker.random_int(1, 5),
            unique_only=False,
        )

    @pytest.fixture
    def urls(self) -> list[str]:
        """Empty list as a fixture to be used by the mock to populate with queried urls"""
        return []
    
    @pytest.fixture(autouse=True)
    def mock_webopen(self, urls: list[str]):
        """Mock for webopen which appends the queried url to the urls fixture list"""
        with patch(f"{MODULE_ROOT}.processors.download.download.webopen", new=urls.append):
            yield

    @pytest.fixture
    def mock_pause(self, model: ItemDownloadHelper) -> Generator[Mock, None, None]:
        """Mock for pause functionality"""
        with patch.object(model, "_run_pause_page") as mock_pause:
            yield mock_pause

    @pytest.fixture
    def unique_tracks(
            self, tracks: list[Track], artists: list[Artist], albums: list[Album], faker: Faker
    ) -> list[Track]:
        """Fixture which returns a list of unique tracks"""
        tracks = list(map(copy, tracks[:10]))

        for track in tracks:
            track.artists = faker.random_elements(artists, length=faker.random_int(1, 3), unique=True)
            track.album = faker.random_element(albums)

        return tracks

    @pytest.fixture
    def duplicate_tracks(self, unique_tracks: list[Track]) -> list[Track]:
        """Fixture which returns a list of tracks with some duplicates present"""
        return unique_tracks * 4

    def test_validate_urls(self):
        with pytest.raises(ValidationError, match="String should match pattern"):
            ItemDownloadHelper(urls=[
                "https://example.com/search?q={}&type=t", "https://example.com/search?q={}&limit={}"
            ])

        with pytest.raises(ValidationError, match="Input should be a valid URL"):
            ItemDownloadHelper(urls=[
                "https://example.com/search?q={}&type=t", "not_a_valid_url_with_placeholder_{}"
            ])

    def test_open_sites_for_collections(self, model: ItemDownloadHelper, playlists: list[Playlist]):
        tracks = tuple(tr for pl in playlists for tr in pl.tracks)

        with patch.object(ItemDownloadHelper, "open_sites") as mock_open_sites:
            model.open_sites_for_collections(playlists)
            mock_open_sites.assert_called_once_with(tracks)

    def test_open_sites_unique_queries(
            self,
            model: ItemDownloadHelper,
            urls: list[str],
            unique_tracks: list[Track],
            duplicate_tracks: list[Track],
            mock_pause: Mock,
    ):
        model.unique_only = True

        model.open_sites(duplicate_tracks)
        assert mock_pause.call_count == math.ceil(len(unique_tracks) / model.interval)
        assert len(urls) == len(unique_tracks) * len(model.urls)

    def test_open_sites_duplicate_queries(
            self,
            model: ItemDownloadHelper,
            urls: list[str],
            unique_tracks: list[Track],
            duplicate_tracks: list[Track],
            mock_pause: Mock,
    ):
        model.unique_only = False

        model.open_sites(duplicate_tracks)
        assert mock_pause.call_count == math.ceil(len(duplicate_tracks) / model.interval)
        assert len(urls) == len(duplicate_tracks) * len(model.urls)

    def test_pause_1(
            self, model: ItemDownloadHelper, urls: list[str], unique_tracks: list[Track], log_capturer: LogCapturer
    ):
        total = len(unique_tracks)
        pages_total = math.ceil(total / model.interval)

        inputs = ["r", "", "name artists", "r", "bad_tag", "r", "name bad_tag", ""] + [""] * total
        with patch_input(iter(inputs)), log_capturer(loggers=model.logger):
            model.open_sites(unique_tracks)

        # 5 extra for 3*r input + 2*<Fields> input
        assert len(urls) == (total + 5 * model.interval) * len(model.urls)

        assert log_capturer.text.count("Enter one of the following") == pages_total
        assert log_capturer.text.count("Some fields were not recognised") == 1
        assert log_capturer.text.count("Unrecognised input") == 1

    def test_pause_2(
            self,
            model: ItemDownloadHelper,
            urls: list[str],
            unique_tracks: list[Track],
            artists: list[Artist],
            albums: list[Album],
            faker: Faker,
            log_capturer: LogCapturer
    ):
        # force a few poison apples
        for item in faker.random_elements(unique_tracks, length=3, unique=True):
            item.artist = None
            item.album = None

        model.fields = ["artists", "album"]
        model.interval = len(unique_tracks)

        inputs = ["h", "artists", "h", "n name", "h", "", "h", "h"]
        with patch_input(iter(inputs)), log_capturer(loggers=model.logger):
            model.open_sites(unique_tracks)

        # Extra:
        # 1*<Fields>*tracks input - 2*3 for poison apples input failing + 3*n<Fields> for poison apples input repeat
        assert len(urls) == (2 * len(unique_tracks) - 3) * len(model.urls)

        assert log_capturer.text.count("Enter one of the following") == 4
        assert log_capturer.text.count("Could not open sites for 3 tracks") == 4
        assert "Some fields were not recognised" not in log_capturer.text
        assert "Unrecognised input" not in log_capturer.text
