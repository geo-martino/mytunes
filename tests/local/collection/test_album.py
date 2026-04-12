import pytest
from faker import Faker

from mytunes.local._collection.album import LocalAlbumCollection
from tests.testers import NoUniqueKeyTester


class TestLocalAlbumCollection(NoUniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> LocalAlbumCollection:
        return LocalAlbumCollection(name=faker.word())
