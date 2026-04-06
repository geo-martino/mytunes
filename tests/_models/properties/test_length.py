from datetime import timedelta

import pytest
from faker import Faker
from pydantic import ValidationError

from musify._models.properties.length import Length
from tests.testers import BaseModelTester


class TestLength(BaseModelTester):
    @pytest.fixture
    def model(self, faker: Faker) -> Length:
        return Length(faker.random_int())

    def test_numeric_representation_conversion(self, model: Length):
        model.root = "12"
        assert int(model) == 12

        model.root = "12.3456"
        assert float(model) == 12.3456

        model.root = "12:34"
        assert int(model) == 12 * 60 + 34

        model.root = "260:12:34"
        assert int(model) == 260 * 60 * 60 + 12 * 60 + 34

        model.root = "12:34,123456"
        assert float(model) == 12 * 60 + 34 + 0.123456

    def test_numeric_representation_conversion_fails(self, model: Length):
        with pytest.raises(ValidationError):
            model.root = "12:34:56:78.90"
        with pytest.raises(ValidationError):
            model.root = "ab:cd"

    def test_timedelta_property(self, model: Length):
        assert Length(359).timedelta == timedelta(seconds=359, milliseconds=0)
        assert Length(360.12).timedelta == timedelta(seconds=360, milliseconds=120)

    def test_to_str(self):
        assert str(Length(359)) == "05:59"
        assert str(Length(360)) == "06:00"
        assert str(Length(360.12)) == "06:00.120"
        assert str(Length(3671)) == "01:01:11"
        assert str(Length(123456)) == "34:17:36"

    def test_ordering(self, model: Length):
        assert model == str(model)
        assert model < str(Length.model_validate(model.root + 2))
        assert model > str(Length.model_validate(model.root - 2))
