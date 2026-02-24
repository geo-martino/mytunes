import pytest
from faker import Faker

# noinspection PyProtectedMember
from musify.models.collection.library import HasTracksAndPlaylists
from musify.models.collection.playlist import Playlist
from musify.models.item.track import Track
from tests.models.testers import MusifyResourceTester


class TestLibrary(MusifyResourceTester):
    @pytest.fixture
    def model(self, faker: Faker) -> HasTracksAndPlaylists:
        return HasTracksAndPlaylists()

    def test_tracks_in_playlists(self, tracks: list[Track], playlists: list[Playlist]):
        for pl in playlists:
            tracks += pl.tracks[:len(pl.tracks) // 2]

        library = HasTracksAndPlaylists(tracks=tracks, playlists=playlists)
        assert all(track not in library.tracks for track in library.tracks_in_playlists)
        assert library.tracks_in_playlists == [track for pl in playlists for track in pl.tracks]
