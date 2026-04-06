import pytest
from faker import Faker

from musify.local._item.artist import LocalArtist
from tests.testers import NoUniqueKeyTester


class TestLocalArtist(NoUniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> LocalArtist:
        return LocalArtist(name=faker.word())
