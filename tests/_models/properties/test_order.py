import pytest
from faker import Faker
from pydantic import ValidationError

from mytunes._models.properties.order import Position
from tests.testers import BaseModelTester


class TestPosition(BaseModelTester):
    @pytest.fixture
    def model(self) -> Position:
        return Position()

    def test_from_number(self, faker: Faker):
        number = faker.random_int(1, 10)
        model = Position.model_validate(number)
        assert model.number == number
        assert model.total is None

    def test_from_numbers(self):
        number = (10,)
        model = Position.model_validate(number)
        assert model.number == 10
        assert model.total is None

        number = (10, 20, 30)
        model = model.model_validate(number)
        assert model.number == 10
        assert model.total == 20

    def test_from_string(self, faker: Faker):
        numbers = "10"
        model = Position.model_validate(numbers)
        assert model.number == 10
        assert model.total is None

        numbers = Position.sep.join(("10", "20"))
        model = model.model_validate(numbers)
        assert model.number == 10
        assert model.total == 20

        numbers = Position.sep.join(("10", "20", "30"))
        model = model.model_validate(numbers)
        assert model.number == 10
        assert model.total == 20

    def test_number_cannot_exceed_total(self, faker: Faker):
        number = faker.random_int(1, 10)
        with pytest.raises(ValidationError):
            Position(number=number, total=number - 1)

    def test_numbers_property(self):
        model = Position(number=10, total=20)
        assert model.numbers == (10, 20)

        model = Position(number=10, total=None)
        assert model.numbers == (10,)

        model = Position(number=None, total=20)
        assert model.numbers == ()

    def test_to_string(self):
        model = Position(number=10, zero_fill=2)
        assert str(model) == "10"

        model = Position(number=10, total=20, zero_fill=4)
        assert str(model) == "0010/0020"

        # zero fill to the length of the total
        model = Position(number=10, total=200, zero_fill=True)
        assert str(model) == "010/200"

        model = Position(number=None, total=200, zero_fill=True)
        assert str(model) == ""

    def test_to_int(self):
        model = Position(number=6, total=10)
        assert int(model) == 6

    def test_ordering(self, faker: Faker):
        model = Position(number=faker.random_int(1, 10), total=10)
        assert model == model.number
        assert model < model.number + 2
        assert model > model.number - 2
