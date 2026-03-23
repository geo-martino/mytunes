import logging
from abc import abstractmethod
from typing import ClassVar, Any, Type

from pydantic import Field, PrivateAttr, validate_call, AliasPath, PositiveInt
from yarl import URL

from musify.exception import MusifyValueError
from musify.models import ResourceModel
from musify.models.api._endpoints import Endpoints, HasEndpoints, HasSavedEndpoints
from musify.models.properties.uri import URI
from musify.models.remote import RemoteResource
from musify.processors_new.clean.string import NameCleaner


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

    cleaner: NameCleaner | None = Field(
        description=(
            "The cleaner to use for cleaning the query parameters generated for an item. "
            "If None, no cleaning will be done. "
            "This doesn't apply to the query string passed to the query method, which is always used as-is."
        ),
        default=None,
    )

    @classmethod
    def _get_query_path(cls, kind: str | Type[RT]) -> str | AliasPath:
        match cls._query_path:
            case None:
                return kind.type
            case str() as path:
                return path.format(type=kind.type)
            case AliasPath() as path:
                kind = cls._map_type_to_str(kind)
                # noinspection PyTypeChecker
                return AliasPath(*(str(part).format(type=kind) for part in path.path))

    @staticmethod
    def _map_type_to_str(kind: str | Type[RT]) -> str:
        match kind:
            case str():
                return kind
            case ResourceModel():
                return kind.type
            case _ if isinstance(kind, type) and issubclass(kind, ResourceModel):
                return kind.type
        raise MusifyValueError(f"Unknown search type: {kind}")

    @validate_call
    async def query(
            self, query: str, types: set[str | Type[RT]], limit: PositiveInt | None = None, **kwargs
    ) -> dict[str, list[RT]]:
        """Query for items of the given types that match the given query parameters."""
        if limit is None:
            limit = self._query_limit

        params = self._format_query_params(query=query, types=types, limit=limit, **kwargs)
        response = await self._handler.get(self._query_url, params=params)

        if "error" in response:
            types_mapped = map(self._map_type_to_str, types)
            message = [f"Query: {query}", f"Types: {",".join(types_mapped)}", response["error"]]
            self._handler.log("SKIP", self._query_url, message=message, level=logging.ERROR)
            return {}

        results: dict[str, list[RT]] = {}
        for kind in types:
            key = self._map_type_to_str(kind)
            path = self._get_query_path(kind=kind)
            items = self._get_items_from_response(response, path=path)
            results[key] = [self.__class__.create_model(it, kind=kind) for it in items]

        return results

    @abstractmethod
    def _format_query_params(
            self, query: str, types: set[Type[ResourceModel]], limit: PositiveInt | None = None, **kwargs
    ) -> dict[str, Any]:
        raise NotImplementedError

    @validate_call
    async def query_item(self, item: ResourceModel, **kwargs) -> list[RT]:
        """Query for items that match the given item."""
        kwargs = self._format_query_from_item(item, **kwargs)
        return next(iter((await self.query(**kwargs)).values()))

    @abstractmethod
    def _format_query_from_item(self, item: ResourceModel, **kwargs) -> dict[str, Any]:
        """Should return the kwargs to pass to _format_query_params"""
        raise NotImplementedError


class HasSearchEndpoints[ET: SearchEndpoints | HasSavedEndpoints](HasEndpoints):
    search: ET = Field(
        description="Access search endpoints for the API."
    )
