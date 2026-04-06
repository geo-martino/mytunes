from random import choice

import pytest

from musify.local._item.genre import LocalGenre
from tests.models.testers import UniqueKeyTester
from tests.utils import GENRES


class TestLocalGenre(UniqueKeyTester):
    @pytest.fixture
    def model(self) -> LocalGenre:
        return LocalGenre(name=choice(GENRES))
