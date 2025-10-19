from random import choice

import pytest
from faker import Faker

from musify.local.item.genre import LocalGenre
from tests.models.testers import UniqueKeyTester
from tests.utils import GENRES


class TestLocalGenre(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> LocalGenre:
        return LocalGenre(name=choice(GENRES))
