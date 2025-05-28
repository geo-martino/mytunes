from random import choice, sample

import pytest
from faker import Faker

from musify.model import MusifyModel
from musify.model.item.genre import Genre, HasGenres
from tests.model.testers import MusifyResourceTester, UniqueKeyTester
from tests.utils import GENRES


class TestGenre(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> MusifyModel:
        return Genre(name=choice(GENRES))


class TestHasGenres(MusifyResourceTester):
    @pytest.fixture
    def model(self, genres: list[Genre]) -> MusifyModel:
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
