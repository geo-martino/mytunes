import pytest

from musify._models.item.genre import Genre
from musify.local._item.genre import LocalGenre
from tests.testers import UniqueKeyTester


class TestLocalGenre(UniqueKeyTester):
    @pytest.fixture
    def model(self, genre: Genre) -> LocalGenre:
        return LocalGenre(name=genre.name)
