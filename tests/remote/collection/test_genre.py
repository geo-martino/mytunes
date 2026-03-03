import pytest
from faker import Faker

from musify.remote.collection.genre import RemoteGenreCollection
from tests.models.testers import UniqueKeyTester
from tests.utils import SimpleURI


class TestRemoteGenreCollection(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> RemoteGenreCollection:
        uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=RemoteGenreCollection.type, source=faker.word()
        )
        return RemoteGenreCollection(name=faker.word(), uri=uri)
