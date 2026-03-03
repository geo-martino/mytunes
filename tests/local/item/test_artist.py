import pytest
from faker import Faker

from musify.local.item.artist import LocalArtist
from musify.models.properties.uri import URI
from tests.models.testers import UniqueKeyTester
from tests.utils import SimpleURI


class TestLocalArtist(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> LocalArtist:
        uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=LocalArtist.type, source=faker.word()
        )
        return LocalArtist(name=faker.word(), uri=uri)
