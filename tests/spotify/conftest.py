import pytest
from faker import Faker

from tests.spotify.generator import SpotifyPayloadGenerator


@pytest.fixture(scope="session")
def generator(faker: Faker) -> SpotifyPayloadGenerator:
    return SpotifyPayloadGenerator(faker)
