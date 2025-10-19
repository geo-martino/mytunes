import pytest
from faker import Faker

from musify.local.collection.genre import LocalGenreCollection
from musify.models.properties.uri import URI
from tests.models.testers import UniqueKeyTester


class TestLocalGenreCollection(UniqueKeyTester):
    @pytest.fixture
    def model(self, uri: URI, faker: Faker) -> LocalGenreCollection:
        return LocalGenreCollection(name=faker.word(), uri=uri)
