import pytest
from faker import Faker

from musify.models.properties.uri import URI
from musify.remote.collection.album import RemoteAlbumCollection
from tests.models.testers import UniqueKeyTester


class TestRemoteAlbumCollection(UniqueKeyTester):
    @pytest.fixture
    def model(self, uri: URI, faker: Faker) -> RemoteAlbumCollection:
        return RemoteAlbumCollection(name=faker.word(), uri=uri)
