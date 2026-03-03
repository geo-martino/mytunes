import pytest
from faker import Faker

from musify.local.collection.genre import LocalGenreCollection
from musify.models.properties.uri import URI
from tests.models.testers import UniqueKeyTester
from tests.utils import SimpleURI


class TestLocalGenreCollection(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> LocalGenreCollection:
        uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=LocalGenreCollection.type, source=faker.word()
        )
        return LocalGenreCollection(name=faker.word(), uri=uri)
