from random import sample

import pytest
from faker import Faker

from musify.models.collection.artist import ArtistCollection
from musify.models.item.album import Album
from tests.models.testers import UniqueKeyTester
from tests.utils import SimpleURI


class TestArtistCollection(UniqueKeyTester):
    @pytest.fixture
    def model(self, albums: list[Album], faker: Faker) -> ArtistCollection:
        uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=ArtistCollection.type
        )
        return ArtistCollection(name=faker.word(), albums=albums, uri=uri)

    def test_artist_name_cannot_be_empty(self, albums: list[Album], faker: Faker):
        with pytest.raises(ValueError, match="no artists found in albums"):
            ArtistCollection()

    def test_albums_must_be_from_same_artist_when_no_name_given(self, albums: list[Album], faker: Faker):
        for album in albums:
            album.artist = faker.word()
        with pytest.raises(ValueError, match="albums are from different artists"):
            ArtistCollection(albums=albums)

    def test_get_artist_name_from_albums(self, albums: list[Album]):
        name = "Test Artist"
        for album in albums:
            album.artist = name

        artist = ArtistCollection(albums=albums)
        assert artist.name == name

    def test_filter_albums_on_artist_name(self, albums: list[Album]):
        name = "Test Artist"
        expected = sample(albums, k=len(albums) // 2)
        for album in expected:
            album.artists = name

        artist = ArtistCollection(name=name, albums=albums)
        assert sorted(artist.albums) == sorted(expected)

    def test_items_count(self, albums: list[Album]):
        name = "Test Album"
        for album in albums:
            album.artist = name

        model = ArtistCollection(name=name, albums=albums)
        assert model.items_count == len(albums)
