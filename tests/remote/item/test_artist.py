import pytest
from faker import Faker

from musify.remote.item.artist import RemoteArtist
from tests.models.testers import UniqueKeyTester
from tests.utils import SimpleURI


class TestRemoteArtist(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> RemoteArtist:
        uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=RemoteArtist.type
        )
        return RemoteArtist(name=faker.word(), uri=uri)
