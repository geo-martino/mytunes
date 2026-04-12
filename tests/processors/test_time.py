from datetime import datetime, timedelta

import pytest
from dateutil.relativedelta import relativedelta
from faker import Faker

from mytunes.processors.time import TimeMapper
from tests.testers import BaseModelTester


class TestTimeMapper(BaseModelTester):
    @pytest.fixture
    def model(self) -> TimeMapper:
        return TimeMapper(unit="days", amount=5, add=True)

    def test_init(self, faker: Faker):
        model = TimeMapper(unit="d", amount=faker.random_int())
        assert model.unit == "days"
        assert model._processor_method == model._days

        model = TimeMapper(unit="__ hours __ ", amount=faker.random_int())
        assert model.unit == "hours"
        assert model._processor_method == model._hours

        model = TimeMapper(unit="__wks__", amount=faker.random_int())
        assert model.unit == "weeks"
        assert model._processor_method == model._weeks

    def test_from_key(self, model: TimeMapper):
        model = model.model_validate("+4h")
        assert model.unit == "hours"
        assert model.amount == 4
        assert model.add
        assert model.key == "+4hours"

        model.key = "20wks"
        assert model.unit == "weeks"
        assert model.amount == 20
        assert not model.add
        assert model.key == "-20weeks"

    def test_key_property(self, model: TimeMapper):
        model.unit = "m"
        model.amount = 20
        model.add = False
        assert model.key == str(model) == "-20minutes"

        model.unit = "s"
        model.add = True
        assert model.key == str(model) == "+20seconds"

    def test_set_by_key(self, model: TimeMapper):
        model.unit = "seconds"
        model.amount = 20
        model.add = False

        model.unit = "-30mins"
        assert model.unit == "minutes"
        assert model.amount == 20  # remains unchanged
        assert not model.add  # remains unchanged

    def test_to_string(self, model: TimeMapper):
        assert str(model) == model.key

    def test_apply_with_timedelta(self, model: TimeMapper):
        model.unit = "hours"
        model.amount = 20
        model.add = False

        dt = datetime.now()
        assert model.apply(dt) == dt - timedelta(hours=20)

    def test_apply_with_relativedelta(self, model: TimeMapper):
        model.unit = "months"
        model.amount = 5
        model.add = True

        dt = datetime.now()
        assert model.apply(dt) == dt + relativedelta(months=5)
