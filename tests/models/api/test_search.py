from collections.abc import Generator
from typing import Any
from unittest.mock import patch, Mock, AsyncMock

import pytest
from aiorequestful.request import RequestHandler
from faker import Faker
from pydantic import PositiveInt
from yarl import URL

from musify.models import ResourceModel
from musify.models.api.search import SearchEndpoints
from musify.models.item.album import RemoteAlbum
from musify.models.item.track import Track, RemoteTrack
from musify.models.remote import RemoteResource
from tests.models.api.testers import EndpointsTester
from tests.models.utils import MockRemoteResource
from tests.utils import SimpleURI


class TestSearchEndpoints(EndpointsTester):
    # noinspection PyAbstractClass
    class MockSearchEndpoints(SearchEndpoints[SimpleURI, MockRemoteResource]):
        _query_url = URL("https://api.example.com/search")
        _query_path = "items"
        _query_limit = 22

    @pytest.fixture
    @patch.multiple(
        MockSearchEndpoints,
        __abstractmethods__=set(),
        _format_query_params=Mock(),
        _format_query_from_item=Mock(),
    )
    def model(self, handler: RequestHandler) -> SearchEndpoints:
        return self.MockSearchEndpoints(handler=handler)

    @pytest.fixture
    def types(self) -> set[type[RemoteResource]]:
        return {RemoteTrack, RemoteAlbum}

    @pytest.fixture
    def mock_query_params(self, model: SearchEndpoints, faker: Faker) -> Generator[Mock, None, None]:
        def _format_query_params(
                query: str, types: set[type[ResourceModel]], limit: PositiveInt | None = None, **kwargs
        ) -> dict[str, Any]:
            params: dict[str, Any] = {"query": query, "types": {t.type for t in types}}
            if limit is not None:
                params["limit"] = limit
            return params | kwargs

        with patch.object(model, "_format_query_params", side_effect=_format_query_params) as mock_params:
            yield mock_params

    async def test_query(
            self,
            model: SearchEndpoints,
            types: set[type[RemoteResource]],
            mock_get: Mock,
            mock_query_params: Mock,
            faker: Faker,
    ):
        query = faker.sentence()
        limit = faker.random_int(1, 50)
        expected_params = {"query": query, "types": {t.type for t in types}, "limit": limit}

        mock_get.return_value = {
            model._query_path: {"tracks": [{"name": faker.name()}], "albums": [{"name": faker.name()}]}
        }

        result = await model.query(query=query, types=types, limit=limit)

        assert set(result.keys()) == {t.type for t in types}
        mock_query_params.assert_called_once_with(query=query, types=types, limit=limit)
        mock_get.assert_called_once_with(model._query_url, params=expected_params)

    async def test_query_uses_default_limit(
            self,
            model: SearchEndpoints,
            types: set[type[RemoteResource]],
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
        expected_query = {"query": query, "types": {RemoteTrack}, "limit": limit}
        expected_params = {"query": query, "types": {RemoteTrack.type}, "limit": limit}

        mock_get.return_value = {model._query_path: {"tracks": [{"name": item.name}]}}

        with patch.object(
                model, "_format_query_from_item", return_value=expected_query
        ) as mock_format_query:
            await model.query_item(item=item, limit=limit)

            mock_format_query.assert_called_once_with(item, limit=limit)
            mock_query_params.assert_called_once_with(**expected_query)
            mock_get.assert_called_once_with(model._query_url, params=expected_params)
