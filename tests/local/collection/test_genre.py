import pytest
from faker import Faker

from mytunes.local._collection.genre import LocalGenreCollection
from tests.testers import UniqueKeyTester


class TestLocalGenreCollection(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> LocalGenreCollection:
        return LocalGenreCollection(name=faker.word())
