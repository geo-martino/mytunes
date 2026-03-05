import pytest
from faker import Faker

from musify.remote.collection import ItemsCursor
from musify.remote.collection.artist import RemoteArtistCollection
from tests.remote.collection.testers import RemoteCollectionTester
from tests.utils import SimpleURI


class TestRemoteArtistCollection(RemoteCollectionTester):
    @pytest.fixture
    def model(self, cursor: ItemsCursor, faker: Faker) -> RemoteArtistCollection:
        uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=RemoteArtistCollection.type, source=faker.word()
        )
        return RemoteArtistCollection(
            name=faker.word(),
            uri=uri,
            total=faker.random_int(1, 20),
            cursor=cursor
        )
