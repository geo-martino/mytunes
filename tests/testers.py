from abc import ABCMeta, abstractmethod
from collections.abc import Hashable
from random import choice
from typing import Callable, Any, Generator
from unittest.mock import Mock, patch, AsyncMock

import math
import pytest
from aiohttp import ClientSession
from aiorequestful.request import RequestHandler
from faker import Faker
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from yarl import URL

from musify._models import BaseModel, ResourceModel
from musify._models.api import Endpoints
from musify._models.properties.uri import URI
from tests.remote import SimpleURI, MockRemoteResource, MockIndexCursor


def assert_validator_skips[T](func: Callable[[T], T], value: T):
    assert func(value) is value


class BaseModelTester(metaclass=ABCMeta):
    """Generic base class for testing :py:class:`.BaseModel` implementations"""
    @abstractmethod
    def model(self, **kwargs) -> BaseModel:
        """Fixture for the models to test"""
        raise NotImplementedError

    @pytest.fixture
    def adapter(self, model: BaseModel) -> TypeAdapter:
        """Fixture for the type adapter to use when validating python objects for this models"""
        return TypeAdapter(model.__class__)

    def test_check_unique_key_tester_enabled(self, model: ResourceModel):
        """Test that the unique key tester is enabled"""
        if isinstance(model, ResourceModel) and model.__unique_attributes__:
            assert isinstance(self, UniqueKeyTester), "Unique keys are configured but UniqueKeyTester is not enabled"
        else:
            assert not isinstance(self, UniqueKeyTester), \
                "Unique keys are not configured but UniqueKeyTester is enabled"

    @staticmethod
    def test_model_registry(model: BaseModel):
        if model.__class__.__final__:
            assert model.__class__ in BaseModel.registered_submodels
        else:
            assert model.__class__ not in BaseModel.registered_submodels


class NoUniqueKeyTester(BaseModelTester, metaclass=ABCMeta):
    """Generic base class for testing :py:class:`.ResourceModel` implementations"""

    @staticmethod
    def test_check_unique_keys(model: BaseModel):
        """Test that the unique keys are set correctly"""
        if not isinstance(model, ResourceModel):
            return pytest.skip("Model is not a ResourceModel, skipping unique key test")

        assert not model.__unique_attributes__, "Unique attributes are not set on the test models"
        assert model.unique_keys == {id(model)}, "ID not found in unique keys"


class UniqueKeyTester(BaseModelTester, metaclass=ABCMeta):
    """Generic base class for testing :py:class:`.ResourceModel` implementations with unique keys set"""
    @staticmethod
    def test_check_unique_keys(model: ResourceModel):
        """Test that the unique keys are set correctly"""
        assert model.__unique_attributes__, "Unique attributes are not set on the test models"
        assert len(model.unique_keys) > 1, "Unique keys not found"

        for key in model.__unique_attributes__:
            if (value := getattr(model, key, None)) is None:
                assert None not in model.unique_keys, "Unique keys should not contain None"
                continue

            assert value in model.unique_keys, f"Value {value} not found in unique keys"
            assert isinstance(value, Hashable)

            try:
                setattr(model, key, None)
                assert value not in model.unique_keys, f"Value {value} should not be in unique keys after removing it"
            except (AttributeError, ValueError):  # value is not mutable or nullable
                pass


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
    def total(self, faker: Faker) -> int:
        return faker.random_int(100, 200)

    @pytest.fixture
    def uri(self, faker: Faker) -> URI:
        return SimpleURI.create_random(MockRemoteResource.type)

    @pytest.fixture
    def uris(self, total: int, faker: Faker) -> list[URI]:
        return [SimpleURI.from_id(i, kind=MockRemoteResource.type) for i in range(total)]

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

        def _return_items(url: URL, **__) -> dict[str, list[dict[str, Any]]]:
            batch_uris = url.query["ids"].split(",")
            batch = [it for it in items if it["uri"] in batch_uris]
            return {items_key: batch}

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
            self, uris: list[URI], limit: int, mocker: MockerFixture
    ) -> Generator[Mock, None, None]:
        mock_batch_values = mocker.spy(Endpoints, "_batch_values")
        yield mock_batch_values
        mock_batch_values.assert_called_once_with(uris, limit)

    @pytest.fixture
    def mock_batch_values_empty(self) -> Generator[Mock, None, None]:
        with patch.object(Endpoints, "_batch_values", return_value=[]) as mock_batch_values:
            yield mock_batch_values

    @pytest.fixture
    def items(self, uris: list[URI], faker: Faker) -> list[dict[str, Any]]:
        return [{"name": faker.word(), "uri": uri} for uri in uris]

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
