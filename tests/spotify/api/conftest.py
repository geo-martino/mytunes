import pytest
from aiohttp import ClientSession
from aiorequestful.request import RequestHandler


@pytest.fixture
def handler() -> RequestHandler:
    return RequestHandler(connector=lambda: ClientSession())
