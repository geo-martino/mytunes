import pytest
from faker import Faker

from musify.local.collection.artist import LocalArtistCollection
from musify.models import MusifyModel
from musify.models.properties.uri import URI
from tests.models.testers import UniqueKeyTester


class TestLocalArtistCollection(UniqueKeyTester):
    @pytest.fixture
    def model(self, uri: URI, faker: Faker) -> MusifyModel:
        return LocalArtistCollection(name=faker.word(), uri=uri)
