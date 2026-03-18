from random import choice, sample

import pytest
from faker import Faker

from musify.models.item.genre import Genre, HasGenres, RemoteGenre
from tests.models.testers import NoUniqueKeyTester, UniqueKeyTester
from tests.utils import GENRES, SimpleURI


class TestGenre(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> Genre:
        return Genre(name=choice(GENRES))


class TestHasGenres(NoUniqueKeyTester):
    @pytest.fixture
    def model(self, genres: list[Genre]) -> HasGenres:
        return HasGenres(genres=genres)

    def test_from_string(self, genres: list[Genre]):
        genre = HasGenres._join_tags(genre.name for genre in genres)
        model = HasGenres(genre=genre)
        assert [genre.name for genre in model.genres] == [genre.name for genre in genres]

    def test_to_string(self, genres: list[Genre]):
        genre = HasGenres._join_tags(genre.name for genre in genres)
        model = HasGenres(genre=genres)
        assert model.genre == genre

    def test_set_genres_on_property(self, model: HasGenres):
        genres = sample(GENRES, k=3)
        model.genre = genres
        assert [genre.name for genre in model.genres] == genres

        model.genre = genres[0]
        assert [genre.name for genre in model.genres] == [genres[0]]


class TestRemoteGenre(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> RemoteGenre:
        uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=RemoteGenre.type
        )
        return RemoteGenre[SimpleURI](name=choice(GENRES), uri=uri)
