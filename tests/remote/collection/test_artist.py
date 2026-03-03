import pytest
from faker import Faker

from musify.remote.collection.artist import RemoteArtistCollection
from tests.models.testers import UniqueKeyTester
from tests.utils import SimpleURI


class TestRemoteArtistCollection(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> RemoteArtistCollection:
        uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=RemoteArtistCollection.type, source=faker.word()
        )
        return RemoteArtistCollection(name=faker.word(), uri=uri)
