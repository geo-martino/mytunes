import pytest
from faker import Faker

from musify.models.properties.uri import URI
from musify.remote.collection.album import RemoteAlbumCollection
from tests.models.testers import UniqueKeyTester
from tests.utils import SimpleURI


class TestRemoteAlbumCollection(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> RemoteAlbumCollection:
        uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=RemoteAlbumCollection.type, source=faker.word()
        )
        return RemoteAlbumCollection(name=faker.word(), uri=uri)
