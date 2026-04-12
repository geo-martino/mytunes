import pytest
from faker import Faker

from mytunes._models.collection.library import RemoteTracksResult
from mytunes._models.collection.playlist import Playlist
from mytunes._models.item.track import RemoteTrack
from tests.testers import BaseModelTester


class TestRemoteTracksResult(BaseModelTester):
    @pytest.fixture
    def model(self) -> RemoteTracksResult:
        return RemoteTracksResult()

    def test_get_tracks_in_collections(self, tracks: list[RemoteTrack], playlists: list[Playlist], faker: Faker):
        for pl in playlists:
            pl.tracks[:] = faker.random_elements(tracks)

        others = faker.random_elements(tracks)
        result = RemoteTracksResult._get_tracks_in_collections(collections=playlists, others=others)
        assert all(track not in others for track in result)

        uris = [track.uri for track in result]
        assert sorted(uris) == sorted(set(uris))  # no duplicates
