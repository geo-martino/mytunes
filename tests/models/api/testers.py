import math
from abc import ABCMeta
from collections.abc import Generator
from random import choice
from typing import Any
from unittest.mock import Mock, patch, AsyncMock

import pytest
from aiohttp import ClientSession
from aiorequestful.request import RequestHandler
from faker import Faker
from pytest_mock import MockerFixture

from musify.models.api import Endpoints
from musify.models.properties.uri import URI
from tests.models.api.utils import MockIndexCursor
from tests.models.testers import BaseModelTester
from tests.models.utils import MockRemoteResource
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
        return SimpleURI.create_random(MockRemoteResource.type)

    @pytest.fixture
    def uris(self, faker: Faker) -> list[URI]:
        return [SimpleURI.from_id(i, kind=MockRemoteResource.type) for i in range(faker.random_int(50, 100))]

    @pytest.fixture
    def limit(self, faker: Faker) -> int:
        return faker.random_int(1, 20)

    @pytest.fixture(autouse=True)
    def mock_create_model(self) -> Generator[Mock, None, None]:
        with patch.object(Endpoints, "create_model", side_effect=lambda x, *_, **__: x) as mock_create_model:
            yield mock_create_model

    @pytest.fixture
    def mock_get(self) -> Generator[Mock, None, None]:
        with patch.object(RequestHandler, "get", new_callable=AsyncMock) as mock_get:
            yield mock_get
            mock_get.assert_called_once()

    @pytest.fixture
    def mock_get_batched(
            self, uris: list[URI], limit: int, items: list[dict[str, Any]], items_key: str, faker: Faker
    ) -> Generator[Mock, None, None]:
        expected = math.ceil(len(uris) / limit)

        def _return_items(*_, **__) -> dict[str, list[dict[str, Any]]]:
            return {items_key: list(faker.random_elements(items, length=limit))}

        with patch.object(RequestHandler, "get", side_effect=_return_items) as mock_get:
            yield mock_get
            assert mock_get.call_count == expected

    @pytest.fixture
    def mock_post_batched(self, uris: list[URI], limit: int) -> Generator[Mock, None, None]:
        expected = math.ceil(len(uris) / limit)

        with patch.object(RequestHandler, "post") as mock_post:
            yield mock_post
            assert mock_post.call_count == expected

    @pytest.fixture
    def mock_put_batched(self, uris: list[URI], limit: int) -> Generator[Mock, None, None]:
        expected = math.ceil(len(uris) / limit)

        with patch.object(RequestHandler, "put") as mock_put:
            yield mock_put
            assert mock_put.call_count == expected

    @pytest.fixture
    def mock_delete_batched(self, uris: list[URI], limit: int) -> Generator[Mock, None, None]:
        expected = math.ceil(len(uris) / limit)

        with patch.object(RequestHandler, "delete") as mock_delete:
            yield mock_delete
            assert mock_delete.call_count == expected

    @pytest.fixture
    def mock_batch_values(
            self, model: Endpoints, uris: list[URI], limit: int, mocker: MockerFixture
    ) -> Generator[Mock, None, None]:
        mock_batch_values = mocker.spy(Endpoints, "_batch_values")
        yield mock_batch_values
        mock_batch_values.assert_called_once_with(uris, limit)

    @pytest.fixture
    def mock_batch_values_empty(self, model: Endpoints) -> Generator[Mock, None, None]:
        with patch.object(Endpoints, "_batch_values", return_value=[]) as mock_batch_values:
            yield mock_batch_values

    @pytest.fixture
    def items(self, total: int, faker: Faker) -> list[dict[str, Any]]:
        return [{"name": faker.word()} for _ in range(total)]

    @pytest.fixture
    def total(self, faker: Faker) -> int:
        return faker.random_int(100, 200)

    @pytest.fixture
    def items_key(self) -> str:
        return "items"

    @pytest.fixture
    def mock_get_all_items(self, items: list[dict[str, Any]], faker: Faker) -> Generator[Mock, None, None]:
        total = faker.random_int(1, 100)
        cursor = MockIndexCursor(
            url=faker.url(), offset=total + 1, limit=faker.random_int(0, 20), total=total
        )

        with patch.object(Endpoints, "_get_all_items", return_value=(items, cursor)) as mock_get_all_items:
            yield mock_get_all_items
            mock_get_all_items.assert_called_once()
