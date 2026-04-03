from abc import ABCMeta
from unittest.mock import patch, Mock, MagicMock

import pytest
from faker import Faker
from pydantic import InstanceOf

from musify.processors.match.score.numeric import NumericScorer, RangeScorer, LengthScorer, ReleaseYearScorer, \
    TotalItemsScorer
from tests.models.testers import BaseModelTester


class NumericScorerTester(BaseModelTester, metaclass=ABCMeta):
    @staticmethod
    def test_calculate_score_returns_on_missing_values(model: NumericScorer):
        assert model._calculate_score(0, 123) == 0
        assert model._calculate_score(123, 0) == 0


class TestStringScoreReducer(BaseModelTester):
    @pytest.fixture
    @patch.multiple(
        RangeScorer,
        __abstractmethods__=set(),
        _calculate_score=MagicMock(),
    )
    def model(self) -> RangeScorer:
        return RangeScorer[InstanceOf[Mock]](type="test", cleaner=Mock(), range=10)

    def test_calculate_score(self, model: RangeScorer, faker: Faker):
        model.range = 10
        assert model._calculate_score(2, 10) == 0.2
        assert model._calculate_score(15, 15) == 1
        assert model._calculate_score(20, 22) == 0.8
        assert model._calculate_score(50, 75) == 0

        model.range = 50
        assert model._calculate_score(2, 10) == 0.84
        assert model._calculate_score(15, 15) == 1
        assert model._calculate_score(20, 22) == 0.96
        assert model._calculate_score(50, 75) == 0.5


class TestLengthScorer(NumericScorerTester):
    @pytest.fixture
    def model(self) -> LengthScorer:
        return LengthScorer()

    def test_calculate_score(self, model: LengthScorer):
        assert model._calculate_score(100, 100) == 1
        assert model._calculate_score(0, 100) == 0
        assert model._calculate_score(50, 100) == 0.5
        assert model._calculate_score(75, 80) == 0.9375
        assert model._calculate_score(5, 10) == 0.5
        assert model._calculate_score(8, 10) == 0.8


class TestReleaseYearScorer(NumericScorerTester):
    @pytest.fixture
    def model(self) -> ReleaseYearScorer:
        return ReleaseYearScorer(range=10)

    def test_calculate_score(self, model: LengthScorer):
        model.range = 10
        assert model._calculate_score(2012, 2012) == 1
        assert model._calculate_score(2012, 2022) == 0
        assert model._calculate_score(2010, 2012) == 0.8
        assert model._calculate_score(1970, 1975) == 0.5


class TestTotalItemsScorer(NumericScorerTester):
    @pytest.fixture
    def model(self) -> TotalItemsScorer:
        return TotalItemsScorer(range=10)

    def test_calculate_score(self, model: TotalItemsScorer):
        assert model._calculate_score(20, 20) == 1
        assert model._calculate_score(10, 20) == 0.5
        assert model._calculate_score(8, 10) == 0.8
        assert model._calculate_score(4, 16) == 0.25
