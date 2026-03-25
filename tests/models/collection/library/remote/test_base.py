from typing import Collection
from unittest.mock import Mock

import pytest

from musify.models.api import RemoteAPI
from musify.models.collection.library import RemoteLibrary
from musify.models.collection.playlist import Playlist
from musify.models.item.album import Album
from musify.models.item.artist import Artist
from musify.models.item.track import Track
from musify.models.remote import RemoteResource
from musify.models.user import RemoteUser
from tests.models.api.utils import MockRemoteAPI
from tests.models.collection.library.remote.utils import MockRemoteLibrary
from tests.models.testers import BaseModelTester


class TestRemoteLibrary(BaseModelTester):

    @pytest.fixture
    def api(self) -> RemoteAPI:
        return MockRemoteAPI()

    @pytest.fixture
    def model(self, api: RemoteAPI, user: RemoteUser) -> RemoteLibrary:
        library = MockRemoteLibrary(api=api)
        library._user = user
        return library

    @staticmethod
    def assert_items_loaded(loaded_items: Collection[RemoteResource], mock_get_all: Mock) -> None:
        """Assert that the given tracks were loaded into the model"""
        mock_get_all.assert_called_once()
        assert len(loaded_items) == len(mock_get_all.return_value)

        expected_uris = sorted(item.uri for item in mock_get_all.return_value)
        assert sorted(item.uri for item in loaded_items) == expected_uris

    async def test_load_playlists(
            self, model: RemoteLibrary, playlists: list[Playlist], user: RemoteUser, mock_get_all: Mock
    ):
        for pl in playlists:
            pl.owner = user

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
