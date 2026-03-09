import pytest
from faker import Faker

from musify.remote.collection import ItemsCursor
from musify.remote.collection.playlist import RemotePlaylist, RemoteMutablePlaylist
from musify.remote.user import RemoteUser
from tests.remote.collection.testers import RemoteCollectionTester
from tests.utils import SimpleURI


class TestRemotePlaylist(RemoteCollectionTester):
    @pytest.fixture
    def model(self, cursor: ItemsCursor, faker: Faker) -> RemotePlaylist:
        playlist_uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=RemotePlaylist.type
        )
        owner_uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=RemoteUser.type
        )
        return RemotePlaylist(
            name=faker.word(),
            owner=RemoteUser(name=faker.user_name(), uri=owner_uri),
            uri=playlist_uri,
            total=faker.random_int(1, 20),
            cursor=cursor
        )


class TestRemoteMutablePlaylist(RemoteCollectionTester):
    @pytest.fixture
    def model(self, cursor: ItemsCursor, faker: Faker) -> RemoteMutablePlaylist:
        playlist_uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=RemotePlaylist.type
        )
        owner_uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=RemoteUser.type
        )
        return RemoteMutablePlaylist(
            name=faker.word(),
            owner=RemoteUser(name=faker.user_name(), uri=owner_uri),
            uri=playlist_uri,
            total=faker.random_int(1, 20),
            cursor=cursor
        )
