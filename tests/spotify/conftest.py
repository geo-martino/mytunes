from collections.abc import Generator
from unittest.mock import patch, AsyncMock

import pytest
from aiohttp import ClientSession
from aiorequestful.auth import Authoriser
from aiorequestful.request import RequestHandler
from faker import Faker
from mytunes.core.api.user import UserEndpoints
from mytunes.spotify._api import SpotifyAPI
from tests.spotify.generator import SpotifyPayloadGenerator


@pytest.fixture(scope="session")
def generator(faker: Faker) -> SpotifyPayloadGenerator:
    return SpotifyPayloadGenerator(faker)


@pytest.fixture(scope="session")
def handler() -> RequestHandler:
    return RequestHandler(connector=lambda: ClientSession())


@pytest.fixture(scope="session")
def api(handler: RequestHandler) -> Generator[SpotifyAPI]:
    with (
        patch.object(Authoriser, "authorise", new_callable=AsyncMock),
        patch.object(UserEndpoints, "get_me", return_value=None, new_callable=AsyncMock)
    ):
        yield SpotifyAPI.model_validate(handler)
