from random import choice

import pytest

from musify.models.properties.uri import URI
from musify.remote.item.genre import RemoteGenre
from tests.models.testers import UniqueKeyTester
from tests.utils import GENRES, SimpleURI


class TestRemoteGenre(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> RemoteGenre:
        uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=RemoteGenre.type, source=faker.word()
        )
        return RemoteGenre(name=choice(GENRES), uri=uri)
