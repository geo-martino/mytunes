import pytest

from mytunes._models.item.genre import Genre
from mytunes.local._item.genre import LocalGenre
from tests.testers import UniqueKeyTester


class TestLocalGenre(UniqueKeyTester):
    @pytest.fixture
    def model(self, genre: Genre) -> LocalGenre:
        return LocalGenre(name=genre.name)
