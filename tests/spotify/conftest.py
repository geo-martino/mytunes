import pytest
from aiohttp import ClientSession
from aiorequestful.request import RequestHandler
from faker import Faker

from mytunes.spotify._api import SpotifyAPI
from tests.spotify.generator import SpotifyPayloadGenerator


@pytest.fixture(scope="session")
def generator(faker: Faker) -> SpotifyPayloadGenerator:
    return SpotifyPayloadGenerator(faker)


@pytest.fixture(scope="session")
def handler() -> RequestHandler:
    return RequestHandler(connector=lambda: ClientSession())


@pytest.fixture(scope="session")
def api(handler: RequestHandler) -> SpotifyAPI:
    return SpotifyAPI.model_validate(handler)
