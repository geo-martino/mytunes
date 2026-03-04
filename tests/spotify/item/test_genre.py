import pytest
from faker import Faker
from pydantic import Json

from musify.spotify.item.genre import SpotifyGenre
from tests.spotify.testers import SpotifyResourceTester
from tests.utils import GENRES


class TestSpotifyGenre(SpotifyResourceTester):
    @pytest.fixture
    def model(self, faker: Faker) -> SpotifyGenre:
        return SpotifyGenre(
            name=faker.random_element(GENRES),
            followers=faker.random_int(0, 100)
        )

    def test_response(self, faker: Faker):
        payload = faker.random_element(GENRES)
        model = SpotifyGenre.model_validate(payload)

        assert model.name == payload
