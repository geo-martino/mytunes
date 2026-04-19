from random import sample

import pytest
from faker import Faker

from mytunes._models.collection.album import AlbumCollection
from mytunes._models.item.album import Album
from mytunes._models.item.track import Track, HasTracks, HasMutableTracks, RemoteTrack
from mytunes._models.properties.order import Position
from tests.remote import SimpleURI
from tests.testers import NoUniqueKeyTester, UniqueKeyTester


class TestTrack(NoUniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> Track:
        return Track(name=faker.sentence().rstrip("."))

    @pytest.fixture
    def tracks(self, album: Album, tracks: list[Track], faker: Faker) -> list[Track]:
        for track in tracks:
            total = faker.random_int(5, 10)

            track.album = album
            track.disc = Position(number=faker.random_int(1, total), total=total)

        return tracks

    def test_set_track_total_from_album(self, tracks: list[Track], faker: Faker):
        # does not attempt to set track.total when not available
        track = Track(name=faker.sentence().rstrip("."), album=Album(name=faker.sentence().rstrip(".")))
        assert track.track is None
        track = Track(name=faker.sentence().rstrip("."), album=AlbumCollection(name=faker.sentence().rstrip(".")))
        assert track.track is None

        album = AlbumCollection(name=tracks[0].album.name, tracks=tracks)
        assert album.track_total == len(tracks)

        track = Track(name=faker.sentence().rstrip("."), album=album)
        assert isinstance(track.track, Position)
        assert track.track.number is None
        assert track.track.total == album.track_total

        track = Track(name=faker.sentence().rstrip("."), album=album, track=5)
        assert track.track.number == 5
        assert track.track.total == album.track_total

    def test_set_disc_total_from_album(self, tracks: list[Track], faker: Faker):
        # does not attempt to set disc.total when not available
        track = Track(name=faker.sentence().rstrip("."), album=Album(name=faker.sentence().rstrip(".")))
        assert track.disc is None
        track = Track(name=faker.sentence().rstrip("."), album=AlbumCollection(name=faker.sentence().rstrip(".")))
        assert track.disc is None

        album = AlbumCollection(name=tracks[0].album.name, tracks=tracks)
        assert album.disc_total == max(track.disc.total for track in tracks)

        track = Track(name=faker.sentence().rstrip("."), album=album)
        assert track.disc is not None
        assert track.disc.number is None
        assert track.disc.total == album.disc_total

        track = Track(name=faker.sentence().rstrip("."), album=album, disc=5)
        assert track.disc.number == 5
        assert track.disc.total == album.disc_total

    def test_equality(self, faker: Faker):
        track = Track(name=faker.sentence().rstrip("."), artist=faker.name(), album=faker.name())
        track_equal = Track(name=track.name, artists=track.artists, album=track.album)
        assert track == track_equal, "Tracks should be equal"

        track_different_name = Track(name=faker.sentence().rstrip("."), artists=track.artists, album=track.album)
        assert track != track_different_name, "Tracks with different names should not be equal"

        track_different_artist = Track(name=track.name, artists=faker.name(), album=track.album)
        assert track != track_different_artist, "Tracks with different artists should not be equal"

        track_different_album = Track(name=track.name, artists=track.artists, album=faker.name())
        assert track != track_different_album, "Tracks with different albums should not be equal"


class TestHasTracks(NoUniqueKeyTester):
    @pytest.fixture
    def model(self, tracks: list[Track]) -> HasTracks:
        return HasTracks(tracks=tracks)

    def test_track_total(self, model: HasTracks):
        assert model.track_total == len(model.tracks), "Track total should be equal to the number of tracks"

    def test_disc_total(self, model: HasTracks, faker: Faker):
        for total in range(1, 6):
            for track in sample(model.tracks, 5):
                track.disc = Position(number=faker.random_int(1, total), total=total)

        assert model.disc_total == 5, "Disc total should be equal to the max number of discs in the tracks"

    def test_disc_total_skips_on_missing_value(self, model: HasTracks, faker: Faker):
        for track in model.tracks:
            track.disc = None

        assert model.disc_total is None


class TestHasMutableTracks(NoUniqueKeyTester):
    @pytest.fixture
    def model(self, tracks: list[Track]) -> HasMutableTracks:
        return HasMutableTracks(tracks=tracks)


class TestRemoteTrack(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> RemoteTrack:
        uri = SimpleURI.create_random(RemoteTrack.type)
        return RemoteTrack(name=faker.word(), uri=uri)
