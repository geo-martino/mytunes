from abc import abstractmethod
from collections.abc import Collection
from typing import ClassVar, Any

from pydantic import Field, PrivateAttr, validate_call, AliasPath, PositiveInt
from yarl import URL

from musify.models import MusifyResource
from musify.models.properties.uri import URI
from musify.remote import RemoteResource
from musify.remote.api._endpoints import RemoteEndpoints, HasEndpoints


# noinspection PyAbstractClass
class SearchEndpoints[UT: URI, RT: RemoteResource](RemoteEndpoints[UT, RT]):
    type: ClassVar[str] = "search"

    _query_url: ClassVar[URL] = PrivateAttr(
        # description="The API endpoint to query for resources.",
    )
    _query_path: ClassVar[None | str | AliasPath] = PrivateAttr(
        # description="The path to the results in the API response.",
    )
    _query_limit: ClassVar[PositiveInt] = PrivateAttr(
        # description="The maximum number of items that can be sent in each request.",
    )

    @property
    def _query_path_parts(self) -> list[str]:
        match self._query_path:
            case None:
                return []
            case str() as path:
                return [path]
            case AliasPath() as path:
                return path.path

    @validate_call
    async def query(self, query: str, types: set[str], limit: PositiveInt | None = None, **kwargs) -> dict[str, list[RT]]:
        """Query for items of the given types that match the given query parameters."""
        if limit is None:
            limit = self._query_limit

        params = self._format_query_params(query=query, types=types, limit=limit, **kwargs)
        response = await self._handler.get(self._query_url, params=params)

        results: dict[str, list[RT]] = {}
        for type in types:
            path = AliasPath(*self._query_path_parts, type)
            print(path, response)
            results[type] = list(self._get_items_from_response(response, path=path, kind=type.rstrip("s")))

        return results

    @staticmethod
    @abstractmethod
    def _format_query_params(
            query: str, types: set[str], limit: PositiveInt | None = None, **kwargs
    ) -> dict[str, Any]:
        raise NotImplementedError

    @validate_call
    async def query_item(self, item: MusifyResource, **kwargs) -> list[RT]:
        """Query for items that match the given item."""
        kwargs = self._format_query_from_item(item, **kwargs)
        return (await self.query(**kwargs))[item.type + "s"]

    @staticmethod
    @abstractmethod
    def _format_query_from_item(item: MusifyResource, **kwargs) -> dict[str, Any]:
        """Should return the kwargs to pass to _format_query_params"""
        raise NotImplementedError


class HasSearchEndpoints[ET: SearchEndpoints](HasEndpoints):
    search: ET = Field(
        description="Access search endpoints for the API."
    )
