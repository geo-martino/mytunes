from abc import ABCMeta

import pytest
from aiohttp import ClientSession
from aiorequestful.request import RequestHandler
from faker import Faker

from musify.models.properties.uri import URI
from tests.models.testers import MusifyModelTester
from tests.remote.api.utils import MockRemoteResource
from tests.utils import SimpleURI


class RemoteEndpointsTester(MusifyModelTester, metaclass=ABCMeta):
    @pytest.fixture
    def handler(self) -> RequestHandler:
        return RequestHandler(connector=lambda: ClientSession())

    @pytest.fixture
    def uri(self, faker: Faker) -> URI:
        return SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=MockRemoteResource.type
        )
