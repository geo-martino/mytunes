import itertools
import math
from abc import ABCMeta
from collections.abc import Generator, Iterable
from random import choice
from typing import Any
from unittest.mock import Mock, patch

import pytest
from aiohttp import ClientSession
from aiorequestful.request import RequestHandler
from faker import Faker

from musify.models.properties.uri import URI
from musify.models.api import Endpoints
from tests.models.testers import BaseModelTester
from tests.models.api.utils import MockRemoteResource
from tests.utils import SimpleURI

URI_TYPE_CONVERTERS = {
    "uri": lambda uri: uri,
    "api_url": lambda uri: uri.api_url,
    "public_url": lambda uri: uri.public_url,
    "uri_str": lambda uri: str(uri),
    "api_url_str": lambda uri: str(uri.api_url),
    "public_url_str": lambda uri: str(uri.public_url),
    "id": lambda uri: uri.id,
    "resource": lambda uri: MockRemoteResource(uri=uri)
}


class EndpointsTester(BaseModelTester, metaclass=ABCMeta):

    @staticmethod
    def _convert_uri_to_random_input_type(value: URI) -> Any:
        return choice(list(URI_TYPE_CONVERTERS.values()))(value)

    @pytest.fixture
    def handler(self) -> RequestHandler:
        return RequestHandler(connector=lambda: ClientSession())

    @pytest.fixture
    def uri(self, faker: Faker) -> URI:
        return SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=MockRemoteResource.type
        )

    @pytest.fixture
    def uris(self, faker: Faker) -> list[URI]:
        return [SimpleURI.from_id(i, kind=MockRemoteResource.type) for i in range(faker.random_int(50, 100))]

    @pytest.fixture
    def limit(self, faker: Faker) -> int:
        return faker.random_int(1, 20)

    @pytest.fixture
    def batches(self, uris: list[URI], limit: int) -> list[tuple[str, ...]]:
        return list(itertools.batched((uri.id for uri in uris), limit))

    @pytest.fixture
    def mock_get(self, uris: list[URI], limit: int) -> Generator[Mock, None, None]:
        expected = math.ceil(len(uris) / limit)

        with patch.object(RequestHandler, "get") as mock_get:
            yield mock_get
            assert mock_get.call_count == expected

    @pytest.fixture
    def mock_post(self, uris: list[URI], limit: int) -> Generator[Mock, None, None]:
        expected = math.ceil(len(uris) / limit)

        with patch.object(RequestHandler, "post") as mock_post:
            yield mock_post
            assert mock_post.call_count == expected

    @pytest.fixture
    def mock_put(self, uris: list[URI], limit: int) -> Generator[Mock, None, None]:
        expected = math.ceil(len(uris) / limit)

        with patch.object(RequestHandler, "put") as mock_put:
            yield mock_put
            assert mock_put.call_count == expected

    @pytest.fixture
    def mock_delete(self, uris: list[URI], limit: int) -> Generator[Mock, None, None]:
        expected = math.ceil(len(uris) / limit)

        with patch.object(RequestHandler, "delete") as mock_delete:
            yield mock_delete
            assert mock_delete.call_count == expected

    @pytest.fixture
    def mock_batch_items(
            self, model: Endpoints, uris: list[URI], batches: list[Iterable[str]], limit: int
    ) -> Generator[Mock, None, None]:
        with patch.object(model.__class__, "_batch_items", return_value=batches) as mock_batch_items:
            yield mock_batch_items
            mock_batch_items.assert_called_once_with(uris, limit)
