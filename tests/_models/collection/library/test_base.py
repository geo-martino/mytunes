import pytest
from faker import Faker

from musify._models.collection.library import HasTracksAndPlaylists
from musify._models.collection.playlist import Playlist
from musify._models.item.track import Track
from tests.testers import NoUniqueKeyTester


class TestLibrary(NoUniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> HasTracksAndPlaylists:
        return HasTracksAndPlaylists()

    def test_items_count(self, tracks: list[Track], playlists: list[Playlist]):
        library = HasTracksAndPlaylists(tracks=tracks, playlists=playlists)
        assert library.count == len(tracks)

    def test_dump(self, model: HasTracksAndPlaylists, playlists: list[Playlist], tracks: list[Track]):
        model = model.__class__(playlists=playlists, tracks=tracks)

        backup = model.dump()
        assert len(backup["playlists"]) == len(model.playlists)
        for pl_id, pl_backup in backup["playlists"].items():
            pl = model.playlists[pl_backup["uri"]]

            assert isinstance(pl_backup, dict)

            assert "name" in pl_backup and isinstance(pl_backup["name"], str)
            assert pl_backup["name"] == pl.name

            assert "tracks" in pl_backup and len(pl_backup["tracks"]) == len(pl.tracks)
            assert all(isinstance(track, dict) for track in pl_backup["tracks"])

            assert "uri" in pl_backup and isinstance(pl_backup["uri"], str)
            assert pl_backup["uri"] == pl.uri

        for track, track_backup in zip(tracks, backup["tracks"]):
            assert isinstance(track_backup, dict)

            assert "name" in track_backup and isinstance(track_backup["name"], str)
            assert track_backup["name"] == track.name

            assert "uri" in track_backup and isinstance(track_backup["uri"], str)
            assert track_backup["uri"] == track.uri
