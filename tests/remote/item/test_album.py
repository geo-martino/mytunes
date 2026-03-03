import pytest
from faker import Faker

from musify.remote.item.album import RemoteAlbum
from tests.models.testers import UniqueKeyTester
from tests.utils import SimpleURI


class TestRemoteAlbum(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> RemoteAlbum:
        uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=RemoteAlbum.type, source=faker.word()
        )
        return RemoteAlbum(name=faker.word(), uri=uri)
