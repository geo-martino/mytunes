import pytest
from faker import Faker

from mytunes.local._collection.artist import LocalArtistCollection
from tests.testers import NoUniqueKeyTester


class TestLocalArtistCollection(NoUniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> LocalArtistCollection:
        return LocalArtistCollection(name=faker.word())
