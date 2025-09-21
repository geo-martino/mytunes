from datetime import datetime, timedelta

import pytest
from dateutil.relativedelta import relativedelta

from musify.processors_new.time import TimeMapper
from tests.models.testers import MusifyModelTester


class TestTimeMapper(MusifyModelTester):
    @pytest.fixture
    def model(self) -> TimeMapper:
        return TimeMapper(unit="days", amount=5, add=True)

    def test_from_key(self, model: TimeMapper) -> None:
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

    def test_key_property(self, model: TimeMapper) -> None:
        model.unit = "m"
        model.amount = 20
        model.add = False
        assert model.key == str(model) == "-20minutes"

        model.unit = "s"
        model.add = True
        assert model.key == str(model) == "+20seconds"

    def test_set_by_key(self, model: TimeMapper) -> None:
        model.unit = "seconds"
        model.amount = 20
        model.add = False

        model.unit = "-30mins"
        assert model.unit == "minutes"
        assert model.amount == 20  # remains unchanged
        assert not model.add  # remains unchanged

    def test_to_string(self, model: TimeMapper) -> None:
        assert str(model) == model.key

    def test_apply_with_timedelta(self, model: TimeMapper) -> None:
        model.unit = "hours"
        model.amount = 20
        model.add = False

        dt = datetime.now()
        assert model.apply(dt) == dt - timedelta(hours=20)

    def test_apply_with_relativedelta(self, model: TimeMapper) -> None:
        model.unit = "months"
        model.amount = 5
        model.add = True

        dt = datetime.now()
        assert model.apply(dt) == dt + relativedelta(months=5)
