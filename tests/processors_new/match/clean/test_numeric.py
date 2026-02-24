from abc import ABCMeta
from unittest.mock import patch, Mock

import pytest

from musify.models.item.album import HasAlbum, Album
from musify.models.properties.length import HasLength
from musify.processors_new.match.clean.numeric import NumericCleaner, LengthCleaner, ReleaseYearCleaner
from tests.models.testers import MusifyModelTester


class NumericCleanerTester(MusifyModelTester, metaclass=ABCMeta):
    @staticmethod
    def test_get_item_value_returns_on_missing_value(model: NumericCleaner):
        assert model._get_item_value(None) == 0


class TestNumericCleaner(MusifyModelTester):
    @pytest.fixture
    @patch.multiple(
        NumericCleaner,
        __abstractmethods__=set(),
        _get_item_value=Mock(),
    )
    def model(self) -> NumericCleaner:
        return NumericCleaner()

    def test_clean_returns_on_missing_value(self, model: NumericCleaner):
        assert model.clean(None) == 0

    def test_round_to_nearest(self, model: NumericCleaner):
        model.round_to_nearest = 0
        assert model.clean(123.45) == 123.45

        model.round_to_nearest = 1
        assert model.clean(123.45) == 123

        model.round_to_nearest = 5
        assert model.clean(123.45) == 125

        model.round_to_nearest = 10
        assert model.clean(123.45) == 120

        model.round_to_nearest = 100
        assert model.clean(123.45) == 100


class TestLengthCleaner(NumericCleanerTester):
    @pytest.fixture
    def model(self) -> LengthCleaner:
        return LengthCleaner()

    def test_get_item_value(self, model: LengthCleaner):
        length = 10
        item = HasLength(length=length)
        assert model._get_item_value(item) == length


class TestReleaseYearCleaner(NumericCleanerTester):
    @pytest.fixture
    def model(self) -> ReleaseYearCleaner:
        return ReleaseYearCleaner()

    def test_get_item_value(self, model: ReleaseYearCleaner):
        year = 2020
        item = HasAlbum(album=Album(name="album 1", released_at=f"{year}-02-04"))
        assert model._get_item_value(item) == year
