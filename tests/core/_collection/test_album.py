from random import sample

import pytest
from faker import Faker
from pydantic import ValidationError

from mytunes.core._collection.album import AlbumCollection, RemoteAlbumCollection
from mytunes.core._item.album import Album
from mytunes.core._item.track import Track
from mytunes.core.cursors import PageCursor
from tests.core._collection.testers import RemoteCollectionTester
from tests.remote import SimpleURI
from tests.testers import NoUniqueKeyTester


class TestAlbumCollection(NoUniqueKeyTester):

    @pytest.fixture
    def model(self, faker: Faker) -> AlbumCollection:
        return AlbumCollection(name=faker.word())

    def test_album_name_cannot_be_empty(self, tracks: list[Track], faker: Faker):
        with pytest.raises(ValidationError, match="no album names found in tracks"):
            AlbumCollection()

    def test_tracks_must_be_from_same_album_when_no_name_given(self, tracks: list[Track], faker: Faker):
        for track in tracks:
            track.album = faker.word()
        with pytest.raises(ValidationError, match="tracks are from different albums"):
            AlbumCollection(tracks=tracks)

    def test_get_album_name_from_tracks(self, tracks: list[Track]):
        album = Album(name="Test Album")
        for track in tracks:
            track.album = album

        collection = AlbumCollection(tracks=tracks)
        assert collection.name == album.name

    def test_filter_tracks_on_album_name(self, tracks: list[Track]):
        album = Album(name="Test Album")
        expected = sample(tracks, k=len(tracks) // 2)
        for track in expected:
            track.album = album

        collection = AlbumCollection(**album.model_dump(), tracks=tracks)
        assert sorted(collection.tracks) == sorted(expected)

    def test_items_count(self, tracks: list[Track]):
        album = Album(name="Test Album")
        for track in tracks:
            track.album = album

        collection = AlbumCollection(**album.model_dump(), tracks=tracks)
        assert collection.count == len(tracks)


class TestRemoteAlbumCollection(RemoteCollectionTester):
    @pytest.fixture
    def model(self, cursor: PageCursor, faker: Faker) -> RemoteAlbumCollection:
        uri = SimpleURI.create_random(RemoteAlbumCollection.type)
        return RemoteAlbumCollection(name=faker.word(), uri=uri, cursor=cursor)
