import pytest
from faker import Faker

from musify.models.properties.order import Position
from tests.models.testers import MusifyModelTester


class TestPosition(MusifyModelTester):
    @pytest.fixture
    def model(self) -> Position:
        return Position()

    # noinspection PyTestUnpassedFixture
    def test_from_number(self, model: Position, faker: Faker):
        number = faker.random_int(1, 10)
        model = model.model_validate(number)
        assert model.number == number
        assert model.total is None

    # noinspection PyTestUnpassedFixture
    def test_from_numbers(self, model: Position):
        number = (10,)
        model = model.model_validate(number)
        assert model.number == 10
        assert model.total is None

        number = (10, 20, 30)
        model = model.model_validate(number)
        assert model.number == 10
        assert model.total == 20

    # noinspection PyTestUnpassedFixture
    def test_from_string(self, model: Position, faker: Faker):
        numbers = "10"
        model = model.model_validate(numbers)
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

    def test_number_cannot_exceed_total(self, model: Position):
        model.total = 5
        with pytest.raises(ValueError):
            model.number = model.total + 1

        with pytest.raises(ValueError):
            Position(number=5, total=4)

    def test_numbers_property(self, model: Position):
        model.number = 10
        model.total = 20
        assert model.numbers == (10, 20)

        model.total = None
        assert model.numbers == (10,)

        model.number = None
        model.total = 20
        assert model.numbers == ()

    def test_to_string(self, model: Position):
        model.number = 10
        model.zero_fill = 2
        assert str(model) == "10"

        model.total = 20
        model.zero_fill = 4
        assert str(model) == "0010/0020"

        model.total = 200
        model.zero_fill = True  # zero fill to the length of the total
        assert str(model) == "010/200"

        model.number = None
        assert str(model) == ""

    def test_to_int(self, model: Position):
        model.number = 6
        assert int(model) == 6

    def test_ordering(self, model: Position, faker: Faker):
        model.number = faker.random_int(1, 10)
        assert model == model.number
        assert model < model.number + 2
        assert model > model.number - 2
