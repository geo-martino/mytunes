from random import choice

import pytest
from faker import Faker

from musify.remote.item.genre import RemoteGenre
from tests.models.testers import UniqueKeyTester
from tests.utils import GENRES


class TestRemoteGenre(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> RemoteGenre:
        return RemoteGenre(name=choice(GENRES))
