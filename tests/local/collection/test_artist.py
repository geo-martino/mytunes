import pytest
from faker import Faker

from musify.local.collection.artist import LocalArtistCollection
from musify.model import MusifyModel
from musify.model.properties.uri import URI
from tests.model.testers import UniqueKeyTester


class TestLocalArtistCollection(UniqueKeyTester):
    @pytest.fixture
    def model(self, uri: URI, faker: Faker) -> MusifyModel:
        return LocalArtistCollection(name=faker.word(), uri=uri)
