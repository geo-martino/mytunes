import pytest
from faker import Faker

from musify.local.collection.album import LocalAlbumCollection
from musify.model import MusifyModel
from musify.model.properties.uri import URI
from tests.model.testers import UniqueKeyTester


class TestLocalAlbumCollection(UniqueKeyTester):
    @pytest.fixture
    def model(self, uri: URI, faker: Faker) -> MusifyModel:
        return LocalAlbumCollection(name=faker.word(), uri=uri)
