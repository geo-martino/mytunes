import pytest
from faker import Faker

from mytunes.core.properties.rating import Rating
from tests.testers import BaseModelTester


class TestRating(BaseModelTester):
    @pytest.fixture
    def model(self, faker: Faker) -> Rating:
        return Rating.model_validate(faker.random_int(0, 100) / 10)
