import pytest
from faker import Faker

from musify.remote.collection.genre import RemoteGenreCollection
from tests.models.testers import UniqueKeyTester
from tests.remote.collection.testers import RemoteCollectionTester
from tests.utils import SimpleURI


class TestRemoteGenreCollection(RemoteCollectionTester):
    @pytest.fixture
    def model(self, cursor: ItemsCursor, faker: Faker) -> RemoteGenreCollection:
        uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=RemoteGenreCollection.type, source=faker.word()
        )
        return RemoteGenreCollection(
            name=faker.word(),
            uri=uri,
            total=faker.random_int(1, 20),
            cursor=cursor
        )
