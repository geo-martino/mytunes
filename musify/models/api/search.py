import logging
from abc import abstractmethod
from typing import ClassVar, Any, Type

from pydantic import Field, PrivateAttr, validate_call, AliasPath, PositiveInt
from yarl import URL

from musify.models import ResourceModel
from musify.models.api._endpoints import Endpoints, HasEndpoints, HasSavedEndpoints
from musify.models.properties.uri import URI
from musify.models.remote import RemoteResource


# noinspection PyAbstractClass
class SearchEndpoints[UT: URI, RT: RemoteResource](Endpoints[UT, RT]):
    type: ClassVar[str] = "search"

    _query_url: ClassVar[URL] = PrivateAttr(
        # description="The API endpoint to query for resources.",
    )
    _query_path: ClassVar[None | str | AliasPath] = PrivateAttr(
        # description=(
        #   "The path to the results in the API response. Use "*" for wildcard matching."
        #   "Use "{type}" to format the resource type"
        # )
    )
    _query_limit: ClassVar[PositiveInt] = PrivateAttr(
        # description="The maximum number of items that can be sent in each request.",
    )

    def _get_query_path(self, kind: Type[RT]) -> str | AliasPath:
        match self._query_path:
            case None:
                return kind.type
            case str() as path:
                return path.format(type=kind.type)
            case AliasPath() as path:
                # noinspection PyTypeChecker
                return AliasPath(*(str(part).format(type=kind.type) for part in path.path))

    @validate_call
    async def query(
            self, query: str, types: set[Type[RT]], limit: PositiveInt | None = None, **kwargs
    ) -> dict[str, list[RT]]:
        """Query for items of the given types that match the given query parameters."""
        if limit is None:
            limit = self._query_limit

        params = self._format_query_params(query=query, types=types, limit=limit, **kwargs)
        response = await self._handler.get(self._query_url, params=params)

        if "error" in response:
            message = [f"Query: {query}", f"Types: {",".join(types)}", response["error"]]
            self._handler.log("SKIP", self._query_url, message=message, level=logging.ERROR)
            return {}

        results: dict[str, list[RT]] = {}
        for kind in types:
            path = self._get_query_path(kind=kind)
            items = self._get_items_from_response(response, path=path)
            results[kind.type] = [self.__class__.create_model(it, kind=kind) for it in items]

        return results

    @staticmethod
    @abstractmethod
    def _format_query_params(
            query: str, types: set[Type[RT]], limit: PositiveInt | None = None, **kwargs
    ) -> dict[str, Any]:
        raise NotImplementedError

    @validate_call
    async def query_item(self, item: ResourceModel, **kwargs) -> list[RT]:
        """Query for items that match the given item."""
        kwargs = self._format_query_from_item(item, **kwargs)
        return next(iter((await self.query(**kwargs)).values()))

    @staticmethod
    @abstractmethod
    def _format_query_from_item(item: ResourceModel, **kwargs) -> dict[str, Any]:
        """Should return the kwargs to pass to _format_query_params"""
        raise NotImplementedError


class HasSearchEndpoints[ET: SearchEndpoints | HasSavedEndpoints](HasEndpoints):
    search: ET = Field(
        description="Access search endpoints for the API."
    )
