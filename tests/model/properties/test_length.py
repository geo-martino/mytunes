from datetime import timedelta

import pytest
from faker import Faker
from pydantic import TypeAdapter

from musify.model import MusifyRootModel, MusifyModel
from musify.model.properties.length import Length
from tests.model.testers import MusifyModelTester


class TestLength(MusifyModelTester):
    @pytest.fixture
    def model(self, faker: Faker) -> MusifyRootModel:
        return Length(faker.random_int())

    def test_numeric_representation_conversion(self, model: Length) -> None:
        model.root = "12"
        assert int(model) == 12

        model.root = "12.3456"
        assert float(model) == 12.3456

        model.root = "12:34"
        assert int(model) == 12 * 60 + 34

        model.root = "260:12:34"
        assert int(model) == 260 * 60 * 60 + 12 * 60 + 34

        model.root = "12:34.123456"
        assert float(model) == 12 * 60 + 34 + 0.123456

    def test_numeric_representation_conversion_fails(self, model: Length) -> None:
        with pytest.raises(ValueError):
            model.root = "12:34:56:78"
        with pytest.raises(ValueError):
            model.root = "ab:cd"

    def test_number_conversion(self, model: Length) -> None:
        model.root = 123.45
        assert int(model) == 123

        model.root = 123
        assert float(model) == 123.0

    def test_timedelta_property(self, model: Length) -> None:
        assert Length(359).timedelta == timedelta(seconds=359, milliseconds=0)
        assert Length(360.12).timedelta == timedelta(seconds=360, milliseconds=120)

    def test_str(self):
        assert str(Length(359)) == "05:59"
        assert str(Length(360)) == "06:00"
        assert str(Length(360.12)) == "06:00.120"
        assert str(Length(3671)) == "1:01:11"
        assert str(Length(123456)) == "34:17:36"
