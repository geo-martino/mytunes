import pytest
from faker import Faker

from musify.models.properties.uri import URI
from musify.remote.item.track import RemoteTrack
from tests.models.testers import UniqueKeyTester


class TestRemoteTrack(UniqueKeyTester):
    @pytest.fixture
    def model(self, uri: URI, faker: Faker) -> RemoteTrack:
        return RemoteTrack(name=faker.word(), uri=uri)
