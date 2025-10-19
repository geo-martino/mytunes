import pytest
from faker import Faker

from musify.local.item.artist import LocalArtist
from musify.models.properties.uri import URI
from tests.models.testers import UniqueKeyTester


class TestArtist(UniqueKeyTester):
    @pytest.fixture
    def model(self, uri: URI, faker: Faker) -> LocalArtist:
        return LocalArtist(name=faker.word(), uri=uri)
