from random import sample

import pytest
from faker import Faker

from musify.models import MusifyModel
from musify.models.collection.album import AlbumCollection
from musify.models.item.track import Track
from musify.models.properties.uri import URI
from tests.models.testers import UniqueKeyTester


class TestAlbumCollection(UniqueKeyTester):

    @pytest.fixture
    def model(self, uri: URI, faker: Faker) -> MusifyModel:
        return AlbumCollection(name=faker.word(), uri=uri)

    def test_album_name_cannot_be_empty(self, tracks: list[Track], faker: Faker):
        with pytest.raises(ValueError, match="no album names found in tracks"):
            AlbumCollection()

    def test_tracks_must_be_from_same_album_when_no_name_given(self, tracks: list[Track], faker: Faker):
        for track in tracks:
            track.album = faker.word()
        with pytest.raises(ValueError, match="tracks are from different albums"):
            AlbumCollection(tracks=tracks)

    def test_get_album_name_from_tracks(self, tracks: list[Track]):
        name = "Test Album"
        for track in tracks:
            track.album = name

        album = AlbumCollection(tracks=tracks)
        assert album.name == name

    def test_filter_tracks_on_album_name(self, tracks: list[Track]):
        name = "Test Album"
        expected = sample(tracks, k=len(tracks) // 2)
        for track in expected:
            track.album = name

        album = AlbumCollection(name=name, tracks=tracks)
        assert sorted(album.tracks) == sorted(expected)
