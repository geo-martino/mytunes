import pytest
from faker import Faker

from mytunes.core._item.track import Track
from mytunes.processors.filters import ValueFilter
from mytunes.processors.tagger.values import FixedValue
from tests.testers import BaseModelTester


class TestFixedValue(BaseModelTester):
    @pytest.fixture
    def model(self, faker: Faker) -> FixedValue:
        return FixedValue(name=faker.word(), value=faker.sentence())

    def test_get_value(self, model: FixedValue, track: Track):
        assert model.get(track) == model.value
        assert model.get(None) == model.value

    def test_applies_filter(self, track: Track, faker: Faker):
        value = faker.random_int()
        condition = ValueFilter(values={track.name})
        assert not condition.check(value)

        model = FixedValue(value=value, condition=condition)
        assert model.get(track) is None
        assert model.get(faker.pystr()) is None
