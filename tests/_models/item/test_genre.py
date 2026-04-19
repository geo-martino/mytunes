import pytest
from faker import Faker

from mytunes._models.item.genre import Genre, HasGenres, RemoteGenre
from tests.remote import SimpleURI
from tests.testers import NoUniqueKeyTester, UniqueKeyTester


class TestGenre(UniqueKeyTester):
    @pytest.fixture
    def model(self, genre: Genre, faker: Faker) -> Genre:
        return Genre(name=genre.name)


class TestHasGenres(NoUniqueKeyTester):
    @pytest.fixture
    def model(self, genres: list[Genre]) -> HasGenres:
        return HasGenres(genres=genres)

    def test_from_string(self, genres: list[Genre]):
        genre = HasGenres._join_tags(genre.name for genre in genres)
        model = HasGenres(genre=genre)
        assert sorted(genre.name for genre in model.genres) == sorted(set(genre.name for genre in genres))

    def test_to_string(self, genres: list[Genre]):
        genre = HasGenres._join_tags(genre.name for genre in genres)
        model = HasGenres(genre=genres)
        assert model.genre == genre

    def test_set_genres_on_property(self, model: HasGenres, genres: list[Genre]):
        model.genre = genres
        assert sorted(genre.name for genre in model.genres) == sorted(set(genre.name for genre in genres))

        model.genre = genres[0]
        assert [genre.name for genre in model.genres] == [genres[0].name]


class TestRemoteGenre(UniqueKeyTester):
    @pytest.fixture
    def model(self, genre: Genre, faker: Faker) -> RemoteGenre:
        uri = SimpleURI.create_random(RemoteGenre.type)
        return RemoteGenre[SimpleURI](name=genre.name, uri=uri)
