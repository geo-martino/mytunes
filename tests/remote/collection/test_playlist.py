import pytest
from faker import Faker

from musify.remote.collection._base import ItemsCursor
from musify.remote.collection.playlist import RemotePlaylist, RemoteMutablePlaylist
from tests.remote.collection.testers import RemoteCollectionTester
from tests.utils import SimpleURI


class TestRemotePlaylist(RemoteCollectionTester):
    @pytest.fixture
    def model(self, cursor: ItemsCursor, faker: Faker) -> RemotePlaylist:
        uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=RemotePlaylist.type, source=faker.word()
        )
        return RemotePlaylist(
            name=faker.word(),
            uri=uri,
            total=faker.random_int(1, 20),
            cursor=cursor
        )


class TestRemoteMutablePlaylist(RemoteCollectionTester):
    @pytest.fixture
    def model(self, cursor: ItemsCursor, faker: Faker) -> RemoteMutablePlaylist:
        uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=RemoteMutablePlaylist.type, source=faker.word()
        )
        return RemoteMutablePlaylist(
            name=faker.word(),
            uri=uri,
            total=faker.random_int(1, 20),
            cursor=cursor
        )
