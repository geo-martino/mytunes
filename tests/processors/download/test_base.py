from collections.abc import Generator
from copy import copy
from unittest.mock import patch, Mock

import math
import pytest
from _pytest.capture import CaptureFixture
from _pytest.logging import LogCaptureFixture
from faker import Faker
from pytest_mock import MockerFixture

from musify import MODULE_ROOT
from musify._models.collection.playlist import Playlist, MutablePlaylist
from musify._models.item.album import Album
from musify._models.item.artist import Artist
from musify._models.item.track import Track
from musify.processors.download import StoreManager
from musify.processors.download._page import StorePausePage
from musify.processors.download.stores import GeneralAudioStore
from musify.processors.download.stores.bandcamp import BandcampStore
from musify.processors.download.stores.juno_download import JunoDownloadStore
from musify.processors.download.stores.qobuz import QobuzStore
from musify.processors.download.stores.seven_digital import SevenDigitalStore
from tests.testers import BaseModelTester
from tests.utils import patch_input


class TestStoreManager(BaseModelTester):

    @pytest.fixture
    def model(self, faker: Faker) -> StoreManager:
        stores = [
            BandcampStore(),
            SevenDigitalStore(locale="en_gb", audio_types=(2, 9)),
            JunoDownloadStore(additional_params={"solrorder": "relevancy"}),
            QobuzStore(locale="en_gb"),
            GeneralAudioStore(
                url="https://www.amazon.com/s?length={}&i=digital-music",
                additional_params={"i": "digital-music"}
            ),
            GeneralAudioStore(
                url="https://www.google.com/search?q={}%20mp3"
            ),
        ]

        return StoreManager(
            stores=faker.random_elements(stores, length=faker.random_int(2, len(stores)), unique=True),
            fields=["name", "artists"],
            interval=faker.random_int(1, 5),
            unique_only=False,
        )

    @pytest.fixture
    def playlists(self, playlists: list[MutablePlaylist], tracks: list[Track], faker: Faker) -> list[MutablePlaylist]:
        for pl in playlists:
            pl.tracks.replace(faker.random_elements(tracks, length=faker.random_int(1, 5)))
        return playlists

    @pytest.fixture
    def urls(self) -> list[str]:
        """Empty list as a fixture to be used by the mock to populate with queried urls"""
        return []
    
    @pytest.fixture(autouse=True)
    def mock_webopen(self, urls: list[str]):
        """Mock for webopen which appends the queried url to the urls fixture list"""
        with patch(f"{MODULE_ROOT}.processors.download._page.webopen", new=urls.append):
            yield

    @pytest.fixture
    def mock_pause(self) -> Generator[Mock, None, None]:
        """Mock for pause functionality"""
        with patch.object(StorePausePage, "pause", return_value=None) as mock_pause:
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

    def test_open_sites_for_collections(
            self,
            model: StoreManager,
            playlists: list[Playlist],
            mock_pause: Mock,
            mocker: MockerFixture,
    ):
        playlists = playlists[:2]
        tracks = tuple(tr for pl in playlists for tr in pl.tracks)

        mock_open_sites_for_items = mocker.spy(StoreManager, "open_sites_for_items")

        model.open_sites_for_collections(playlists)
        mock_open_sites_for_items.assert_called_once_with(model, items=tracks)

    def test_open_sites_unique_queries(
            self,
            model: StoreManager,
            urls: list[str],
            unique_tracks: list[Track],
            duplicate_tracks: list[Track],
            mock_pause: Mock,
    ):
        model.unique_only = True

        model.open_sites_for_items(duplicate_tracks)
        assert mock_pause.call_count == math.ceil(len(unique_tracks) / model.interval)
        assert len(urls) == len(unique_tracks) * len(model.stores)

    def test_open_sites_duplicate_queries(
            self,
            model: StoreManager,
            urls: list[str],
            unique_tracks: list[Track],
            duplicate_tracks: list[Track],
            mock_pause: Mock,
    ):
        model.unique_only = False

        model.open_sites_for_items(duplicate_tracks)
        assert mock_pause.call_count == math.ceil(len(duplicate_tracks) / model.interval)
        assert len(urls) == len(duplicate_tracks) * len(model.stores)

    def test_pause(
            self,
            model: StoreManager,
            urls: list[str],
            unique_tracks: list[Track],
            mocker: MockerFixture,
            caplog: LogCaptureFixture,
    ):
        total = len(unique_tracks)
        pages_total = math.ceil(total / model.interval)
        mock_pause = mocker.spy(StorePausePage, "pause")

        inputs = ["r", "", "name artists", "r", "bad_tag", "r", "name bad_tag", ""] + [""] * total
        with patch_input(iter(inputs)):
            model.open_sites_for_items(unique_tracks)

        # 5 extra for 3*r input + 2*<Fields> input
        assert len(urls) == (total + 5 * model.interval) * len(model.stores)

        assert mock_pause.call_count == pages_total + 2
        assert caplog.text.count("Some fields were not recognised") == 1
        assert caplog.text.count("Unrecognised input") == 1
