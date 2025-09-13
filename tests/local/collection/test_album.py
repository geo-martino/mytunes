import pytest
from faker import Faker

from musify.local.collection.album import LocalAlbumCollection
from musify.models import MusifyModel
from musify.models.properties.uri import URI
from tests.models.testers import UniqueKeyTester


class TestLocalAlbumCollection(UniqueKeyTester):
    @pytest.fixture
    def model(self, uri: URI, faker: Faker) -> MusifyModel:
        return LocalAlbumCollection(name=faker.word(), uri=uri)
