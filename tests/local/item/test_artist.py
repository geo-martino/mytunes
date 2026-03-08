import pytest
from faker import Faker

from musify.local.item.artist import LocalArtist
from tests.models.testers import UniqueKeyTester
from tests.utils import SimpleURI


class TestLocalArtist(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> LocalArtist:
        uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=LocalArtist.type
        )
        return LocalArtist(name=faker.word(), uri=uri)
