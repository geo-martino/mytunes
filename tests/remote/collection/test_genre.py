import pytest
from faker import Faker

from musify.models.properties.uri import URI
from musify.remote.collection.genre import RemoteGenreCollection
from tests.models.testers import UniqueKeyTester


class TestRemoteGenreCollection(UniqueKeyTester):
    @pytest.fixture
    def model(self, uri: URI, faker: Faker) -> RemoteGenreCollection:
        return RemoteGenreCollection(name=faker.word(), uri=uri)
