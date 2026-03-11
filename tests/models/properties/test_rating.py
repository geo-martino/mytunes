import pytest
from faker import Faker

from musify.models.properties.rating import Rating
from tests.models.testers import BaseModelTester


class TestRating(BaseModelTester):
    @pytest.fixture
    def model(self, faker: Faker) -> Rating:
        return Rating.model_validate(faker.random_int(0, 100) / 10)
