import pytest
from faker import Faker

from musify.models.properties.uri import URI
from musify.remote.item.track import RemoteTrack
from tests.models.testers import UniqueKeyTester
from tests.utils import SimpleURI


class TestRemoteTrack(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> RemoteTrack:
        uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=RemoteTrack.type, source=faker.word()
        )
        return RemoteTrack(name=faker.word(), uri=uri)
