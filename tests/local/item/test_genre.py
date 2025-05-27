from random import choice

import pytest
from faker import Faker

from musify.model import MusifyModel
from musify.local.item.genre import LocalGenre
from tests.model.testers import UniqueKeyTester
from tests.utils import GENRES


class TestLocalGenre(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> MusifyModel:
        return LocalGenre(name=choice(GENRES))
