from collections.abc import Collection
from unittest.mock import Mock

import pytest

from mytunes.core.api import RemoteAPI
from mytunes.core._collection.library import RemoteLibrary
from mytunes.core._collection.playlist import RemotePlaylist
from mytunes.core._item.album import Album
from mytunes.core._item.artist import Artist
from mytunes.core._item.track import Track
from mytunes.core._item.user import RemoteUser
from mytunes.core.remote import RemoteResource
from tests.core._collection.library.remote.utils import MockRemoteLibrary
from tests.remote import MockRemoteAPI
from tests.testers import BaseModelTester


class TestRemoteLibrary(BaseModelTester):

    @pytest.fixture
    def api(self) -> RemoteAPI:
        return MockRemoteAPI()

    @pytest.fixture
    def model(self, api: RemoteAPI, user: RemoteUser) -> RemoteLibrary:
        library = MockRemoteLibrary(api=api)
        library.api.users._user = user
        return library

    @staticmethod
    def assert_items_loaded(loaded_items: Collection[RemoteResource], mock_get_all: Mock) -> None:
        """Assert that the given tracks were loaded into the model"""
        mock_get_all.assert_called_once()
        assert len(loaded_items) == len(mock_get_all.return_value)

        expected_uris = sorted(item.uri for item in mock_get_all.return_value)
        assert sorted(item.uri for item in loaded_items) == expected_uris

    async def test_load_playlists(
            self, model: RemoteLibrary, playlists: list[RemotePlaylist], user: RemoteUser, mock_get_all: Mock
    ):
        playlists = [pl.model_copy(update=dict(owner=user)) for pl in playlists]

        mock_get_all.return_value = playlists
        assert await model.load_playlists()

        self.assert_items_loaded(list(model.playlists.unique), mock_get_all)

    async def test_load_library_tracks(self, model: RemoteLibrary, tracks: list[Track], mock_get_all: Mock):
        mock_get_all.return_value = tracks
        assert await model.load_tracks()
        self.assert_items_loaded(model.tracks, mock_get_all)

    async def test_load_library_artists(self, model: RemoteLibrary, artists: list[Artist], mock_get_all: Mock):
        mock_get_all.return_value = artists
        assert await model.load_library_artists()
        self.assert_items_loaded(model.artists, mock_get_all)

    async def test_load_library_albums(self, model: RemoteLibrary, albums: list[Album], mock_get_all: Mock):
        mock_get_all.return_value = albums
        assert await model.load_library_albums()
        self.assert_items_loaded(model.albums, mock_get_all)
