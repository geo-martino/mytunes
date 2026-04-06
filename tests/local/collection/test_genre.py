import pytest
from faker import Faker

from musify.local._collection.genre import LocalGenreCollection
from tests.models.testers import UniqueKeyTester
from tests.utils import SimpleURI


class TestLocalGenreCollection(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> LocalGenreCollection:
        uri = SimpleURI.create_random(LocalGenreCollection.type)
        return LocalGenreCollection(name=faker.word(), uri=uri)
