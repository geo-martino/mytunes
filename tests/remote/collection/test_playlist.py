import pytest
from faker import Faker

from musify.remote.collection.playlist import RemotePlaylist, RemoteMutablePlaylist
from tests.models.testers import UniqueKeyTester
from tests.utils import SimpleURI


class TestPlaylist(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> RemotePlaylist:
        uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=RemotePlaylist.type, source=faker.word()
        )
        return RemotePlaylist(name=faker.sentence(), uri=uri)


class TestMutablePlaylist(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> RemoteMutablePlaylist:
        uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=RemoteMutablePlaylist.type, source=faker.word()
        )
        return RemoteMutablePlaylist(name=faker.sentence(), uri=uri)
