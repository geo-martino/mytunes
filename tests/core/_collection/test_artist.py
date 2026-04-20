from random import sample

import pytest
from faker import Faker
from pydantic import ValidationError

from mytunes.core._collection.artist import ArtistCollection, RemoteArtistCollection
from mytunes.core._item.album import Album
from mytunes.core._item.artist import Artist
from mytunes.core.cursors import PageCursor
from tests.core._collection.testers import RemoteCollectionTester
from tests.remote import SimpleURI
from tests.testers import NoUniqueKeyTester


class TestArtistCollection(NoUniqueKeyTester):
    @pytest.fixture
    def model(self, albums: list[Album], faker: Faker) -> ArtistCollection:
        return ArtistCollection(name=faker.word(), albums=albums)

    def test_artist_name_cannot_be_empty(self, albums: list[Album], faker: Faker):
        with pytest.raises(ValidationError, match="no artists found in albums"):
            ArtistCollection()

    def test_albums_must_be_from_same_artist_when_no_name_given(self, albums: list[Album], faker: Faker):
        for album in albums:
            album.artist = faker.word()
        with pytest.raises(ValidationError, match="albums are from different artists"):
            ArtistCollection(albums=albums)

    def test_get_artist_name_from_albums(self, albums: list[Album]):
        artist = Artist(name="Test Artist")
        for album in albums:
            album.artist = artist

        collection = ArtistCollection(albums=albums)
        assert collection.name == artist.name

    def test_filter_albums_on_artist_name(self, albums: list[Album]):
        artist = Artist(name="Test Artist")
        expected = sample(albums, k=len(albums) // 2)
        for album in expected:
            album.artist = artist

        collection = ArtistCollection(**artist.model_dump(), albums=albums)
        assert sorted(collection.albums) == sorted(expected)

    def test_items_count(self, albums: list[Album]):
        artist = Artist(name="Test Artist")
        for album in albums:
            album.artist = artist

        collection = ArtistCollection(**artist.model_dump(), albums=albums)
        assert collection.count == len(albums)


class TestRemoteArtistCollection(RemoteCollectionTester):
    @pytest.fixture
    def model(self, cursor: PageCursor, faker: Faker) -> RemoteArtistCollection:
        uri = SimpleURI.create_random(RemoteArtistCollection.type)
        return RemoteArtistCollection(name=faker.word(), uri=uri, cursor=cursor)
