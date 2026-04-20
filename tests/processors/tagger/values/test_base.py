import pytest
from faker import Faker

from mytunes.core._item.track import Track
from mytunes.processors.tagger.values import FixedValue
from tests.testers import BaseModelTester


class TestFixedValue(BaseModelTester):
    @pytest.fixture
    def model(self, faker: Faker) -> FixedValue:
        return FixedValue(name=faker.word(), value=faker.sentence())

    def test_get_value(self, model: FixedValue, track: Track):
        assert model.get(track) == model.value
        assert model.get(None) == model.value
