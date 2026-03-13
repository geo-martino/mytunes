from random import sample

import pytest
from faker import Faker

from musify.models.collection.album import AlbumCollection, RemoteAlbumCollection
from musify.models.cursors import PageCursor
from musify.models.item.track import Track
from tests.models.collection.testers import RemoteCollectionTester
from tests.models.testers import UniqueKeyTester
from tests.utils import SimpleURI


class TestAlbumCollection(UniqueKeyTester):

    @pytest.fixture
    def model(self, faker: Faker) -> AlbumCollection:
        uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=AlbumCollection.type
        )
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

    def test_items_count(self, tracks: list[Track]):
        name = "Test Album"
        for track in tracks:
            track.album = name

        model = AlbumCollection(name=name, tracks=tracks)
        assert model.count == len(tracks)


class TestRemoteAlbumCollection(RemoteCollectionTester):
    @pytest.fixture
    def model(self, cursor: PageCursor, faker: Faker) -> RemoteAlbumCollection:
        uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=RemoteAlbumCollection.type
        )
        return RemoteAlbumCollection(
            name=faker.word(),
            uri=uri,
            total=faker.random_int(1, 20),
            cursor=cursor
        )
