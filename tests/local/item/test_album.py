import pytest
from faker import Faker

from musify.local.item.album import LocalAlbum
from musify.models.properties.uri import URI
from tests.models.testers import UniqueKeyTester


class TestLocalAlbum(UniqueKeyTester):
    @pytest.fixture
    def model(self, uri: URI, faker: Faker) -> LocalAlbum:
        return LocalAlbum(name=faker.word(), uri=uri)
