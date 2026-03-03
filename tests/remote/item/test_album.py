import pytest
from faker import Faker

from musify.remote.item.album import RemoteAlbum
from musify.models.properties.uri import URI
from tests.models.testers import UniqueKeyTester


class TestRemoteAlbum(UniqueKeyTester):
    @pytest.fixture
    def model(self, uri: URI, faker: Faker) -> RemoteAlbum:
        return RemoteAlbum(name=faker.word(), uri=uri)
