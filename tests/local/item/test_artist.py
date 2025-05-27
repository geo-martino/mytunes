import pytest
from faker import Faker

from musify.model import MusifyModel
from musify.local.item.artist import LocalArtist
from musify.model.properties.uri import URI
from tests.model.testers import MusifyResourceTester, UniqueKeyTester


class TestArtist(UniqueKeyTester):
    @pytest.fixture
    def model(self, uri: URI, faker: Faker) -> MusifyModel:
        return LocalArtist(name=faker.word(), uri=uri)
