import pytest
from faker import Faker

from musify.spotify.collection.library import SpotifyLibrary
from tests.models.testers import MusifyModelTester


class TestSpotifyLibrary(MusifyModelTester):
    @pytest.fixture
    def model(self, faker: Faker) -> SpotifyLibrary:
        return SpotifyLibrary(
            name=faker.name(),
            followers=faker.random_int(),
        )
