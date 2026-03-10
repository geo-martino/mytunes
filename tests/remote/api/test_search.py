from collections.abc import Generator
from unittest.mock import patch, Mock, AsyncMock

import pytest
from aiorequestful.request import RequestHandler
from faker import Faker
from yarl import URL

from musify.models.item.track import Track
from musify.remote.api.search import SearchEndpoints
from tests.remote.api.testers import RemoteEndpointsTester
from tests.remote.api.utils import MockRemoteResource
from tests.utils import SimpleURI


class TestSearchEndpoints(RemoteEndpointsTester):
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

    async def test_query(self, model: SearchEndpoints, faker: Faker):
        query = faker.sentence()
        types = {"tracks", "albums"}
        limit = faker.random_int(1, 50)

        params = {"query": query, "types": {"track", "album"}, "limit": limit}
        response = {model._query_path: {"tracks": [{"name": faker.name()}], "albums": [{"name": faker.name()}]}}

        with (
            patch.object(model.__class__, "_format_query_params", return_value=params) as mock_format_query,
            patch.object(RequestHandler, "get", return_value=response, new_callable=AsyncMock) as mock_get,
            patch.object(model.__class__, "create_model", return_value={"name": faker.name()}) as mock_create_model,
        ):
            result = await model.query(query=query, types=types, limit=limit)

            assert set(result.keys()) == types
            mock_format_query.assert_called_once_with(query=query, types=types, limit=limit)
            mock_get.assert_called_once_with(model._query_url, params=params)

    async def test_query_uses_default_limit(self, model: SearchEndpoints, faker: Faker):
        query = faker.sentence()
        types = {"tracks", "albums"}
        response = {model._query_path: {"tracks": [], "albums": []}}

        with (
            patch.object(model.__class__, "_format_query_params", return_value={}) as mock_format_query,
            patch.object(RequestHandler, "get", return_value=response, new_callable=AsyncMock),
            patch.object(model.__class__, "create_model", return_value={"name": faker.name()}),
        ):
            await model.query(query=query, types=types)
            mock_format_query.assert_called_once_with(query=query, types=types, limit=model._query_limit)

    async def test_query_item(self, model: SearchEndpoints, faker: Faker):
        item = Track(name=faker.name())
        limit = faker.random_int(1, 50)
        query = {"query": f"track:{item.name}", "types": {"tracks"}, "limit": limit}

        response = {"tracks": [{"name": item.name}]}

        with (
            patch.object(model.__class__, "_format_query_from_item", return_value=query) as mock_format_query,
            patch.object(model.__class__, "query", return_value=response, new_callable=AsyncMock) as mock_query,
        ):
            await model.query_item(item=item, limit=limit)

            mock_format_query.assert_called_once_with(item, limit=limit)
            mock_query.assert_called_with(**query)
