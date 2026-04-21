import logging
from abc import abstractmethod
from typing import ClassVar, Any, Type, Union, get_args, get_origin

from mytunes._types import get_generic
from mytunes.core.api import HasLibraryEndpoints
from mytunes.core.api._endpoints import Endpoints, HasEndpoints
from mytunes.core.properties.name import HasName
from mytunes.core.properties.uri import URI
from mytunes.core.remote import RemoteResource
from mytunes.exception import MyTunesTypeError, RequestError
from mytunes.processors.clean.string import NameCleaner
from pydantic import Field, PrivateAttr, validate_call, AliasPath, PositiveInt, AliasChoices
from yarl import URL

from ..._base.resource import ResourceModel


# noinspection PyAbstractClass
class SearchEndpoints[UT: URI, RT: RemoteResource, QT: ResourceModel](Endpoints[UT, RT]):
    _query_url: ClassVar[URL] = PrivateAttr(
        # description="The API endpoint to query for resources.",
    )
    _query_path: ClassVar[None | str | AliasPath | AliasChoices] = PrivateAttr(
        # description=(
        #   "The path to the results in the API response. Use '*' for wildcard matching."
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

    @property
    def supported_search_types(self) -> set[str]:
        kls = get_generic(type(self), expected=RemoteResource, base=Endpoints)
        if get_origin(kls) is Union:
            return {arg.type for arg in get_args(kls)}
        return {kls.type}

    @validate_call
    async def query(
            self, query: str, types: set[str], limit: PositiveInt | None = None, **kwargs
    ) -> dict[str, list[RT]]:
        """Query for items of the given types that match the given query parameters."""
        if limit is None:
            limit = self._query_limit

        supported_types = types & self.supported_search_types  # filter to only supported types
        if not supported_types:
            raise MyTunesTypeError(f"Unknown search types: {self._logger.format_list_to_string(types)}")

        params = self._format_query_params(query=query, types=supported_types, limit=limit, **kwargs)
        response = await self._handler.get(self._query_url, params=params)

        if "error" in response:
            message = [f"Query: {query}", f"Types: {",".join(supported_types)}", response["error"]]
            self._handler.log("SKIP", self._query_url, message=message, level=logging.ERROR)
            return {}

        results: dict[str, list[RT]] = {}
        for item_type in supported_types:
            path = self._get_query_path(self._query_path, item_type=item_type)
            items = self._get_items_from_response(response, path=path)
            results[item_type] = [type(self).create_model(it, context=self._model_context) for it in items if it]

        return results

    @abstractmethod
    def _format_query_params(
            self, query: str, types: set[str | Type[QT]], limit: PositiveInt | None = None, **kwargs
    ) -> dict[str, Any]:
        raise NotImplementedError

    @classmethod
    def _get_query_path[T: str | AliasPath | AliasChoices](cls, path: T | None, item_type: str) -> T:
        match path:
            case None:
                return item_type
            case str() as key:
                return key.format(type=item_type)
            case AliasPath() as alias:
                # noinspection PyTypeChecker
                return AliasPath(*(str(part).format(type=item_type) for part in alias.path))
            case AliasChoices() as choices:
                return AliasChoices(*(cls._get_query_path(alias, item_type) for alias in iter(choices.choices)))

        raise RequestError(f"Unknown query path type: {path}")

    @validate_call
    async def query_item(self, item: QT, **kwargs) -> list[RT]:
        """Query for items that match the given item."""
        kwargs = self._format_query_from_item(item, **kwargs)
        return next(iter((await self.query(**kwargs)).values()))

    @abstractmethod
    def _format_query_from_item(self, item: QT, **kwargs) -> dict[str, Any]:
        """Should return the kwargs to pass to _format_query_params"""
        raise NotImplementedError

    def _get_name(self, item: HasName) -> str:
        return self.cleaner.clean(item.name) if self.cleaner is not None else item.name


class HasSearchEndpoints[ET: SearchEndpoints | HasLibraryEndpoints](HasEndpoints):
    search: ET = Field(
        description="Access search endpoints for the API."
    )
