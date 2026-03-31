from abc import ABCMeta
from unittest.mock import patch, Mock

import pytest
from faker import Faker

from musify.exception import MusifyTypeError
from musify.models.collection.album import AlbumCollection
from musify.models.item.album import HasAlbum, Album
from musify.models.item.track import HasTracks, Track
from musify.models.properties.length import HasLength
from musify.processors.clean.numeric import NumericCleaner, LengthCleaner, ReleaseYearCleaner, \
    TotalItemsCleaner
from tests.models.testers import BaseModelTester
from tests.processors.utils import MockCollection


class NumericCleanerTester(BaseModelTester, metaclass=ABCMeta):
    @staticmethod
    def test_get_item_value_basic(model: NumericCleaner):
        item = 123
        assert model._get_item_value(item) == item

        item = 123.45
        assert model._get_item_value(item) == item

    @staticmethod
    def test_get_item_value_returns_on_missing_value(model: NumericCleaner):
        assert model._get_item_value(None) == 0

    @staticmethod
    def test_get_item_value_fails(model: NumericCleaner):
        with pytest.raises(MusifyTypeError):
            model._get_item_value("invalid item")


class TestNumericCleaner(BaseModelTester):
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
        assert model._get_item_value(item.length) == length
        assert model._get_item_value(float(item.length)) == length


class TestReleaseYearCleaner(NumericCleanerTester):
    @pytest.fixture
    def model(self) -> ReleaseYearCleaner:
        return ReleaseYearCleaner()

    def test_get_item_value(self, model: ReleaseYearCleaner):
        year = 2020
        item = HasAlbum(album=Album(name="album 1", released_at=f"{year}-02-04"))

        assert model._get_item_value(item) == year
        assert model._get_item_value(item.album) == year
        assert model._get_item_value(item.album.released_at) == year
        assert model._get_item_value(item.album.released_at.year) == year


class TestTotalItemsCleaner(NumericCleanerTester):
    @pytest.fixture
    def model(self) -> TotalItemsCleaner:
        return TotalItemsCleaner()

    def test_get_item_value(self, model: TotalItemsCleaner, tracks: list[Track], faker: Faker):
        item = MockCollection(name=faker.name(), all_items=tracks)

        assert model._get_item_value(item) == item.count == len(tracks)
        assert model._get_item_value(list(item.items)) == item.count == len(tracks)
