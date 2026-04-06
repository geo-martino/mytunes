import pytest
from faker import Faker

from musify.local._item.album import LocalAlbum
from tests.testers import NoUniqueKeyTester


class TestLocalAlbum(NoUniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> LocalAlbum:
        return LocalAlbum(name=faker.word())
