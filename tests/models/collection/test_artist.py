from random import sample

import pytest
from faker import Faker
from pydantic import ValidationError

from musify.models.collection.artist import ArtistCollection, RemoteArtistCollection
from musify.models.cursors import PageCursor
from musify.models.item.album import Album
from musify.models.item.artist import Artist
from tests.models.collection.testers import RemoteCollectionTester
from tests.models.testers import NoUniqueKeyTester
from tests.utils import SimpleURI


class TestArtistCollection(NoUniqueKeyTester):
    @pytest.fixture
    def model(self, albums: list[Album], faker: Faker) -> ArtistCollection:
        uri = SimpleURI.create_random(ArtistCollection.type)
        return ArtistCollection(name=faker.word(), albums=albums, uri=uri)

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
        return RemoteArtistCollection(
            name=faker.word(),
            uri=uri,
            total=faker.random_int(1, 20),
            cursor=cursor
        )
