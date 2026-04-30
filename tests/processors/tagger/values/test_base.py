import pytest
from faker import Faker

from mytunes.core._item.track import Track
from mytunes.processors.compare import Comparer
from mytunes.processors.filters import ValueFilter, ComparerFilter
from mytunes.processors.tagger.values import FixedValue
from processors.tagger.values.testers import ValueTester
from tests.testers import BaseModelTester


class TestFixedValue(ValueTester):
    @pytest.fixture
    def model(self, faker: Faker) -> FixedValue:
        return FixedValue(name=faker.word(), value=faker.sentence())

    def test_get_value(self, model: FixedValue, track: Track):
        assert model.get(track) == model.value
        assert model.get(None) == model.value

    def test_applies_filter(self, track: Track, condition: ComparerFilter, faker: Faker):
        assert not condition.check(track)

        model = FixedValue(value=faker.random_int(), condition=condition)
        assert model.get(track) is None
