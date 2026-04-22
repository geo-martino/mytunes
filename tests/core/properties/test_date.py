from datetime import date, timedelta

import pytest
from faker import Faker
from pydantic import ValidationError

from mytunes.core.properties.date import SparseDate
from tests.testers import BaseModelTester


class TestSparseDate(BaseModelTester):
    @pytest.fixture
    def model(self, faker: Faker) -> SparseDate:
        return SparseDate(year=faker.year())

    def test_validate_month_not_set_when_day_set(self, model: SparseDate, faker: Faker):
        with pytest.raises(ValidationError, match="Cannot set day"):
            SparseDate(year=faker.year(), day=faker.random_int(min=1, max=28))

    def test_from_date(self, model: SparseDate):
        model = model.model_validate("2025-03-01")
        assert model.year == 2025
        assert model.month == 3
        assert model.day == 1

        model = model.model_validate(date(2025, 3, 1))
        assert model.year == 2025
        assert model.month == 3
        assert model.day == 1

    def test_from_string(self, model: SparseDate):
        model = model.model_validate("2025-03")
        assert model.year == 2025
        assert model.month == 3
        assert model.day is None

        model = model.model_validate("2025")
        assert model.year == 2025
        assert model.month is None
        assert model.day is None

    def test_date_property(self, model: SparseDate, faker: Faker):
        model = SparseDate(year=faker.year())
        assert model.date is None

        model = SparseDate(year=model.year, month=faker.random_int(min=1, max=12))
        assert model.date is None

        model = SparseDate(year=model.year, month=model.month, day=faker.random_int(min=1, max=28))
        assert model.date == date(year=model.year, month=model.month, day=model.day)

    def test_to_string(self, model: SparseDate):
        model = SparseDate(year=2025, month=3, day=1)
        assert str(model) == "2025-03-01"

        model = SparseDate(year=model.year, month=model.month)
        assert str(model) == "2025-03"

        model = SparseDate(year=model.year)
        assert str(model) == "2025"

    def test_equality(self):
        model = SparseDate(year=2024, month=3, day=12)

        assert model == model
        assert model == date(2024, 3, 12)
        assert model == "2024-03-12"

    def test_ordering(self, model: SparseDate, faker: Faker):
        model_date = date(year=model.year, month=model.month or 1, day=model.day or 1)
        assert model < model.model_copy(update=dict(year=model.year + 2))
        assert model < model_date + timedelta(days=1)
        assert model > (model_date - timedelta(days=1)).isoformat()
