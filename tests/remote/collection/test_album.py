import pytest
from faker import Faker

from musify.remote.collection._base import ItemsCursor
from musify.remote.collection.album import RemoteAlbumCollection
from tests.models.testers import UniqueKeyTester
from tests.remote.collection.testers import RemoteCollectionTester
from tests.utils import SimpleURI


class TestRemoteAlbumCollection(RemoteCollectionTester):
    @pytest.fixture
    def model(self, cursor: ItemsCursor, faker: Faker) -> RemoteAlbumCollection:
        uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=RemoteAlbumCollection.type, source=faker.word()
        )
        return RemoteAlbumCollection(
            name=faker.word(),
            uri=uri,
            total=faker.random_int(1, 20),
            cursor=cursor
        )
