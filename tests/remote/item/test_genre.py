from random import choice

import pytest
from faker import Faker

from musify.remote.item.genre import RemoteGenre
from tests.models.testers import UniqueKeyTester
from tests.utils import GENRES, SimpleURI


class TestRemoteGenre(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> RemoteGenre:
        uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=RemoteGenre.type
        )
        return RemoteGenre[SimpleURI](name=choice(GENRES), uri=uri)
