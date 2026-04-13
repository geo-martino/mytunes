from collections.abc import Generator
from typing import Any
from unittest.mock import patch, Mock, AsyncMock

import pytest
from aiorequestful.request import RequestHandler
from faker import Faker
from mytunes._models.api.search import SearchEndpoints
from mytunes._models.item.album import RemoteAlbum
from mytunes._models.item.track import Track, RemoteTrack
from mytunes._models.remote import RemoteResource
from pydantic import PositiveInt, AliasPath, AliasChoices
from tests.remote import MockSearchEndpoints
from tests.testers import EndpointsTester


class TestSearchEndpoints(EndpointsTester):
    @pytest.fixture
    def model(self, handler: RequestHandler) -> SearchEndpoints:
        return MockSearchEndpoints(handler=handler)

    @pytest.fixture
    def types(self) -> set[str]:
        return {RemoteTrack.type, RemoteAlbum.type}

    # noinspection PyMethodOverriding
    @pytest.fixture
    def mock_get(self, model: SearchEndpoints, faker: Faker) -> Generator[Mock, None, None]:
        response = {
            model._query_path.path[0]: {"tracks": [{"name": faker.name()}], "albums": [{"name": faker.name()}]}
        }

        with patch.object(RequestHandler, "get", return_value=response, new_callable=AsyncMock) as mock_get:
            yield mock_get
            mock_get.assert_called_once()

    @pytest.fixture
    def mock_query_params(self, model: SearchEndpoints, faker: Faker) -> Generator[Mock, None, None]:
        def _format_query_params(
                query: str, types: set[str], limit: PositiveInt | None = None, **kwargs
        ) -> dict[str, Any]:
            params: dict[str, Any] = {"query": query, "types": types}
            if limit is not None:
                params["limit"] = limit
            return params | kwargs

        with patch.object(model, "_format_query_params", side_effect=_format_query_params) as mock_params:
            yield mock_params

    @pytest.fixture
    def kind(self, faker: Faker) -> type[RemoteResource]:
        return faker.random_element([RemoteTrack, RemoteAlbum])

    def test_get_query_path_on_none(self, kind: type[RemoteResource]):
        assert SearchEndpoints._get_query_path(None, kind.type) is kind.type

    def test_get_query_path_on_key(self, kind: type[RemoteResource], faker: Faker):
        key = "items_{type}s"
        assert SearchEndpoints._get_query_path(key, kind.type) == f"items_{kind.type}s"

    def test_get_query_path_on_path(self, kind: type[RemoteResource], faker: Faker):
        path = AliasPath("items", "{type}s")
        assert SearchEndpoints._get_query_path(path, kind.type) == AliasPath("items", f"{kind.type}s")

    def test_get_query_path_on_choices(self, kind: type[RemoteResource], faker: Faker):
        choices = AliasChoices(
            "items_{type}s",
            AliasPath("items", "{type}s"),
        )
        assert SearchEndpoints._get_query_path(choices, kind.type) == AliasChoices(
            f"items_{kind.type}s",
            AliasPath("items", f"{kind.type}s")
        )

    async def test_query(
            self,
            model: SearchEndpoints,
            types: set[str],
            mock_get: Mock,
            mock_query_params: Mock,
            faker: Faker,
    ):
        query = faker.sentence()
        limit = faker.random_int(1, 50)
        expected_params = {"query": query, "types": types, "limit": limit}

        result = await model.query(query=query, types=types, limit=limit)

        assert set(result.keys()) == types
        mock_query_params.assert_called_once_with(query=query, types=types, limit=limit)
        mock_get.assert_called_once_with(model._query_url, params=expected_params)

    async def test_query_uses_default_limit(
            self,
            model: SearchEndpoints,
            types: set[str],
            mock_get: Mock,
            mock_query_params: Mock,
            faker: Faker,
    ):
        query = faker.sentence()

        await model.query(query=query, types=types)
        mock_query_params.assert_called_once_with(query=query, types=types, limit=model._query_limit)

    async def test_query_item(
            self,
            model: SearchEndpoints,
            mock_get: Mock,
            mock_query_params: Mock,
            faker: Faker
    ):
        item = Track(name=faker.name())

        query = f"track:{item.name}"
        limit = faker.random_int(1, 50)
        expected_query = {"query": query, "types": {RemoteTrack.type}, "limit": limit}
        expected_params = {"query": query, "types": {RemoteTrack.type}, "limit": limit}

        with patch.object(
                model, "_format_query_from_item", return_value=expected_query
        ) as mock_format_query:
            await model.query_item(item=item, limit=limit)

            mock_format_query.assert_called_once_with(item, limit=limit)
            mock_query_params.assert_called_once_with(**expected_query)
            mock_get.assert_called_once_with(model._query_url, params=expected_params)
