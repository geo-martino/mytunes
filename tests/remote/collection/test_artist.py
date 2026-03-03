import pytest
from faker import Faker

from musify.models.properties.uri import URI
from musify.remote.collection.artist import RemoteArtistCollection
from tests.models.testers import UniqueKeyTester


class TestRemoteArtistCollection(UniqueKeyTester):
    @pytest.fixture
    def model(self, uri: URI, faker: Faker) -> RemoteArtistCollection:
        return RemoteArtistCollection(name=faker.word(), uri=uri)
