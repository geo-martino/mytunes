import pytest
from faker import Faker

from musify.models.api import RemoteAPI
# noinspection PyProtectedMember
from musify.models.collection.library import HasTracksAndPlaylists, RemoteLibrary, RemoteMutableLibrary
from musify.models.collection.playlist import Playlist
from musify.models.item.track import Track
from tests.models.api.utils import MockRemoteAPI
from tests.models.testers import BaseResourceTester, BaseModelTester


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
        assert library.items_count == len(tracks)


class TestRemoteLibrary(BaseModelTester):

    @pytest.fixture
    def api(self) -> RemoteAPI:
        return MockRemoteAPI()

    @pytest.fixture
    def model(self, api: RemoteAPI) -> RemoteLibrary:
        return RemoteLibrary(api=api)


class TestRemoteMutableLibrary(BaseModelTester):
    @pytest.fixture
    def api(self) -> RemoteAPI:
        return MockRemoteAPI()

    @pytest.fixture
    def model(self, api: RemoteAPI) -> RemoteMutableLibrary:
        return RemoteMutableLibrary(api=api)
