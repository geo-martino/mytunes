import pytest
from faker import Faker

from musify.model import MusifyModel
from musify.model.item.artist import Artist, HasArtists
from musify.model.properties.uri import URI
from tests.model.testers import MusifyResourceTester, UniqueKeyTester


class TestArtist(UniqueKeyTester):
    @pytest.fixture
    def model(self, uri: URI, faker: Faker) -> MusifyModel:
        return Artist(name=faker.word(), uri=uri)


class TestHasArtists(MusifyResourceTester):
    @pytest.fixture
    def model(self, artists: list[Artist]) -> MusifyModel:
        return HasArtists(artists=artists)

    def test_from_string(self, artists: list[Artist]):
        artist = HasArtists._join_tags(artist.name for artist in artists)
        model = HasArtists(artist=artist)
        assert [artist.name for artist in model.artists] == [artist.name for artist in artists]

    def test_to_string(self, artists: list[Artist]):
        artist = HasArtists._join_tags(artist.name for artist in artists)
        model = HasArtists(artist=artists)
        assert model.artist == artist

    def test_set_artists_on_property(self, model: HasArtists, faker: Faker):
        artists = [faker.word() for _ in range(faker.random_int(2, 5))]
        model.artist = artists
        assert [artist.name for artist in model.artists] == artists

        model.artist = artists[0]
        assert [artist.name for artist in model.artists] == [artists[0]]
