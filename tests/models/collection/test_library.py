from collections.abc import Collection
from typing import ClassVar, Generator
from unittest.mock import patch, Mock

import pytest
from faker import Faker

from musify.models.api import RemoteAPI, ReadSavedEndpoints
from musify.models.collection import PageCursor
# noinspection PyProtectedMember
from musify.models.collection.library import HasTracksAndPlaylists, RemoteLibrary, RemoteMutableLibrary
from musify.models.collection.playlist import Playlist, RemotePlaylist
from musify.models.item.album import Album
from musify.models.item.artist import Artist
from musify.models.item.track import Track
from musify.models.remote import RemoteResource
from musify.models.user import RemoteUser
from tests.models.api.utils import MockRemoteAPI
from tests.models.testers import BaseResourceTester, BaseModelTester
from tests.utils import SimpleURI


class TestLibrary(BaseResourceTester):
    @pytest.fixture
    def model(self, faker: Faker) -> HasTracksAndPlaylists:
        return HasTracksAndPlaylists()

    def test_tracks_in_playlists(self, tracks: list[Track], playlists: list[Playlist]):
        for pl in playlists:
            tracks += pl.tracks[:len(pl.tracks) // 2]

        library = HasTracksAndPlaylists(tracks=tracks, playlists=playlists)
        assert all(track not in library.tracks for track in library.tracks_in_playlists)
        assert library.tracks_in_playlists == [track for pl in playlists for track in pl.tracks]

    def test_items_count(self, tracks: list[Track], playlists: list[Playlist]):
        library = HasTracksAndPlaylists(tracks=tracks, playlists=playlists)
        assert library.count == len(tracks)


class MockRemoteLibrary(RemoteLibrary):
    source: ClassVar[str] = "test"


class TestRemoteLibrary(BaseModelTester):

    @pytest.fixture
    def api(self) -> RemoteAPI:
        return MockRemoteAPI()

    @pytest.fixture
    def user(self, faker: Faker) -> RemoteUser:
        owner_uri = SimpleURI.from_id(faker.pystr(22, 22), kind=RemoteUser.type)
        return RemoteUser(name=faker.name(), uri=owner_uri)

    @pytest.fixture
    def model(self, api: RemoteAPI, user: RemoteUser) -> RemoteLibrary:
        library = MockRemoteLibrary(api=api)
        library._user = user
        return library

    @pytest.fixture
    def playlists(self, playlists: list[Playlist], user: RemoteUser, faker: Faker) -> list[RemotePlaylist]:
        return [
            RemotePlaylist(**pl.model_dump(), owner=user, cursor=PageCursor(url=faker.url()))
            for pl in playlists
        ]

    @pytest.fixture
    def mock_get_all(self) -> Generator[Mock, None, None]:
        with patch.object(ReadSavedEndpoints, "get_all") as mock_get_all:
            yield mock_get_all

    @staticmethod
    def assert_items_loaded(loaded_items: Collection[RemoteResource], mock_get_all: Mock) -> None:
        """Assert that the given tracks were loaded into the model"""
        mock_get_all.assert_called_once()
        assert len(loaded_items) == len(mock_get_all.return_value)
        assert [item.uri for item in loaded_items] == [item.uri for item in mock_get_all.return_value]

    async def test_load_playlists(self, model: RemoteLibrary, playlists: list[Playlist], mock_get_all: Mock):
        mock_get_all.return_value = playlists
        assert await model.load_playlists()
        self.assert_items_loaded(model.playlists.values(), mock_get_all)

    async def test_load_saved_tracks(self, model: RemoteLibrary, tracks: list[Track], mock_get_all: Mock):
        mock_get_all.return_value = tracks
        assert await model.load_tracks()
        self.assert_items_loaded(model.tracks, mock_get_all)

    async def test_load_saved_artists(self, model: RemoteLibrary, artists: list[Artist], mock_get_all: Mock):
        mock_get_all.return_value = artists
        assert await model.load_saved_artists()
        self.assert_items_loaded(model.artists, mock_get_all)

    async def test_load_saved_albums(self, model: RemoteLibrary, albums: list[Album], mock_get_all: Mock):
        mock_get_all.return_value = albums
        assert await model.load_saved_albums()
        self.assert_items_loaded(model.albums, mock_get_all)


class TestRemoteMutableLibrary(BaseModelTester):
    class MockRemoteMutableLibrary(RemoteMutableLibrary):
        pass

    @pytest.fixture
    def api(self) -> RemoteAPI:
        return MockRemoteAPI()

    @pytest.fixture
    def model(self, api: RemoteAPI) -> RemoteMutableLibrary:
        return self.MockRemoteMutableLibrary(api=api)
