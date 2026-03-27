from abc import ABCMeta, abstractmethod
from collections.abc import Iterable
from typing import Any
from urllib.parse import unquote

import pytest

from musify.libraries.remote.core.types import RemoteObjectType
from musify.libraries.remote.spotify.api import SpotifyAPI
from musify.libraries.remote.spotify.base import SpotifyItem, SpotifyObject
from musify.libraries.remote.spotify.object import SpotifyCollectionLoader, SpotifyArtist
from tests.libraries.remote.core.object import RemoteCollectionTester
from tests.libraries.remote.spotify.api.mock import SpotifyMock


class SpotifyCollectionLoaderTester(RemoteCollectionTester, metaclass=ABCMeta):

    @abstractmethod
    def collection_merge_items(self, *args, **kwargs) -> Iterable[SpotifyItem]:
        raise NotImplementedError

    @abstractmethod
    def item_kind(self, api: SpotifyAPI) -> RemoteObjectType:
        """Yields the RemoteObjectType of items in this collection as a pytest.fixture."""
        raise NotImplementedError

    @pytest.fixture
    def item_key(self, item_kind: RemoteObjectType) -> str:
        """Yields the key of items in this collection as a pytest.fixture."""
        return item_kind.name.lower() + "s"

    ###########################################################################
    ## Assertions
    ###########################################################################
    @staticmethod
    async def assert_load_with_items_requests[T: SpotifyObject](
            response: dict[str, Any],
            result: SpotifyCollectionLoader[T],
            items: list[T],
            key: str,
            api_mock: SpotifyMock,
    ):
        """Run assertions on the requests from load method with given ``items``"""
        assert len(result.response[key][result.api.items_key]) == response[key]["total"]
        assert len(result.items) == response[key]["total"]
        assert not await api_mock.get_requests(url=result.url)  # main collection URL was not called

        # ensure none of the input_ids were requested
        input_ids = {item.id for item in items}
        for url, _, _ in await api_mock.get_requests(url=f"{result.url}/{key}"):
            if "ids" not in url.query:
                continue

            assert not input_ids.intersection(unquote(url.query["ids"]).split(","))

    @staticmethod
    async def assert_load_with_items_extended[T: SpotifyObject](
            response: dict[str, Any],
            result: SpotifyCollectionLoader[T],
            items: list[T],
            kind: RemoteObjectType,
            key: str,
            api_mock: SpotifyMock,
    ):
        """Run assertions on the requests for missing data from load method with given ``items``"""
        requests_missing = await api_mock.get_requests(url=f"{result.api.url}/{key}")
        limit = response[key]["limit"]
        input_ids = {item.id for item in items}
        response_item_ids = {
            item[key.rstrip("s")]["id"] if kind == RemoteObjectType.PLAYLIST else item["id"]
            for item in response[key][result.api.items_key]
        }
        assert len(requests_missing) == api_mock.calculate_pages(limit=limit, total=len(response_item_ids - input_ids))

    ###########################################################################
    ## Tests
    ###########################################################################
    @staticmethod
    @abstractmethod
    async def get_load_without_items(
            loader: SpotifyCollectionLoader,
            response_valid: dict[str, Any],
            api: SpotifyAPI,
            api_mock: SpotifyMock
    ):
        """Yields the results from 'load' where no items are given as a pytest.fixture."""
        raise NotImplementedError

    async def test_load_without_items(
            self,
            collection: SpotifyCollectionLoader,
            response_valid: dict[str, Any],
            item_key: str,
            api: SpotifyAPI,
            api_mock: SpotifyMock
    ):
        result = await self.get_load_without_items(
            loader=collection, response_valid=response_valid, api=api, api_mock=api_mock
        )

        assert result.name == response_valid["name"]
        assert result.id == response_valid["id"]
        assert str(result.url) == response_valid["href"]

        expected = api_mock.calculate_pages_from_response(result.response, item_key=item_key)
        if not isinstance(result, SpotifyArtist):
            expected -= 1  # -1 for not calling initial page

        assert len(await api_mock.get_requests(url=result.url)) == 1
        assert len(await api_mock.get_requests(url=f"{result.url}/{item_key}")) == expected
        assert not await api_mock.get_requests(url=f"{api.url}/audio-features")
        assert not await api_mock.get_requests(url=f"{api.url}/audio-analysis")

        # input items given, but no key to search on still loads
        result = await collection.load(response_valid, api=api, items=response_valid.pop(item_key), extend_tracks=True)

        assert result.name == response_valid["name"]
        assert result.id == response_valid["id"]
        assert str(result.url) == response_valid["href"]
