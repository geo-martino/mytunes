import pytest
from faker import Faker

from musify.local._collection.genre import LocalGenreCollection
from tests.remote import SimpleURI
from tests.testers import UniqueKeyTester


class TestLocalGenreCollection(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> LocalGenreCollection:
        uri = SimpleURI.create_random(LocalGenreCollection.type)
        return LocalGenreCollection(name=faker.word(), uri=uri)
