import pytest
from faker import Faker

from musify.models.properties.uri import URI
from musify.remote.item.artist import RemoteArtist
from tests.models.testers import UniqueKeyTester


class TestRemoteArtist(UniqueKeyTester):
    @pytest.fixture
    def model(self, uri: URI, faker: Faker) -> RemoteArtist:
        return RemoteArtist(name=faker.word(), uri=uri)
