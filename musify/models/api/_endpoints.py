import itertools
from collections.abc import Iterable, Sequence, Mapping
from copy import copy
from itertools import batched
from typing import Any, ClassVar, Self, Type, Union

from aiorequestful.auth import Authoriser
from aiorequestful.request import RequestHandler
from aiorequestful.types import JSON
from pydantic import Field, InstanceOf, AliasPath, PositiveInt, validate_call, TypeAdapter, \
    PrivateAttr, model_validator, ModelWrapValidatorHandler
from pydantic_core import PydanticUndefined
from yarl import URL

from musify.exception import MusifyTypeError
from musify.models._base import AttributeModelMetaclass
from musify.models.api.exception import APIError
from musify.models.api.types import ApiURL, _ApiURLSchema, _ApiURISchema, ApiURISequence
from musify.models.collection import RemoteCollection
from musify.models.cursors import PageCursor, HasPageCursor, IterablePageCursor, IndexCursor, InitialCursor
from musify.models.properties.logger import HasLogger
from musify.models.properties.uri import URI
from musify.models.remote import RemoteModel, RemoteResource


class EndpointsMetaclass(AttributeModelMetaclass):
    def create_model(cls: type[Endpoints], value: Any, kind: str | type = None) -> RemoteResource:
        """Create an instance of the resource type handled by this API model from the given value."""
        if not cls.__final__:
            raise MusifyTypeError("Can only create resources from final API models.")

        if isinstance(kind, type) and issubclass(kind, RemoteResource) and kind.__final__:
            # just try to create the resource directly if a final resource type is given
            return kind.model_validate(value)

        if kind is None:
            kind = cls.type

        # noinspection PyTypeChecker
        source_classes = [kls for kls in RemoteResource.registered_submodels if kls.source == cls.source]
        if not source_classes:
            raise MusifyTypeError(f"No registered resource models found for source {cls.source!r}.")

        if isinstance(kind, str):
            type_classes = [kls for kls in source_classes if kls.type == kind]
        else:
            type_classes = [kls for kls in source_classes if issubclass(kls, kind)]
            kind = kind.__name__
        if not type_classes:
            raise MusifyTypeError(f"Could not find a registered {cls.source!r} model for type {kind!r}.")

        return TypeAdapter(Union[*type_classes]).validate_python(value)


class Endpoints[UT: URI, RT: RemoteResource](RemoteModel, HasLogger, metaclass=EndpointsMetaclass):
    type: ClassVar[str | Type[RemoteResource]] = Field(
        description="The type of resources the endpoints of this API model handle.",
    )
    _bar_threshold: ClassVar[int] = PrivateAttr(
        # description="The minimum number of pages required to show a progress bar when paginating through items.",
        default=5,
    )

    _handler: InstanceOf[RequestHandler[Authoriser, JSON]] = PrivateAttr(
        # description="The handler for the API endpoint.",
    )

    @model_validator(mode="wrap")
    @classmethod
    def _from_handler[T](cls, value: T | RequestHandler, handler: ModelWrapValidatorHandler[Self]) -> Self:
        key = "handler"
        if isinstance(value, Mapping) and set(value.keys()) == {key}:
            value = value[key]
        if not isinstance(value, RequestHandler):
            return handler(value)

        data = {name: {key: value} for name in cls.model_fields.keys()}  # nested endpoints
        self = handler(data)
        self._handler = value
        return self

    @staticmethod
    def _batch_items(uris: Iterable, limit: int) -> batched[str]:
        """Batch the given URIs into sublists of the given size."""
        return itertools.batched(map(str, uris), limit)

    @classmethod
    def _generate_batch_url(cls, base_url: URL, values: Iterable) -> URL:
        """Generate a URL for the API endpoint for batched requests."""
        return base_url.update_query(ids=",".join(map(str, values)))

    # noinspection PyArgumentList
    @validate_call
    async def _get_all_items(
            self,
            cursor: PageCursor,
            path: str | AliasPath,
            kind: str | Type | None = None,
    ) -> tuple[tuple[RT, ...], PageCursor]:
        """Get all items from a request with paginated responses using the fastest available method."""
        if isinstance(cursor, IterablePageCursor):
            return await self._get_all_items_by_generation(cursor=cursor, path=path, kind=kind)
        return await self._get_all_items_by_pagination(cursor=cursor, path=path, kind=kind)

    @validate_call
    async def _get_all_items_by_pagination(
            self,
            cursor: PageCursor,
            path: str | AliasPath,
            kind: str | Type | None = None,
    ) -> tuple[tuple[RT, ...], PageCursor]:
        """
        Get all items by paginating through the cursor, which must have a next URL for the first page of items.

        This is usually the slower approach, but is more widely supported as it does not require the API
        to provide the total number of items, offset and limit in the page cursor.
        """
        items: list[RT] = []
        while cursor.next is not None:
            # noinspection PyUnresolvedReferences
            response = await self._handler.get(cursor.next.url)

            response_items = self._get_items_from_response(response=response, path=path)
            items.extend(self.__class__.create_model(it, kind=kind) for it in response_items)

            cursor = cursor.get_cursor_from_response(response=response, path=path)

            if cursor.next == cursor:
                raise APIError("Cursor next URL is the same as the current page URL, cannot paginate further.")

            if isinstance(cursor, IterablePageCursor):
                # switch to faster generation mode for the remaining pages
                # noinspection PyArgumentList
                response_items, cursor = await self._get_all_items_by_generation(cursor=cursor, path=path, kind=kind)
                items.extend(response_items)
                break

        return tuple(items), cursor

    @validate_call
    async def _get_all_items_by_generation[T: IterablePageCursor](
            self, cursor: T, path: str | AliasPath, kind: str | Type[RT] | None = None,
    ) -> tuple[tuple[RT, ...], T]:
        """
        Get all items by generating the next cursors for the next pages of items and sending requests
        for them asynchronously.

        This is usually the faster approach, but is only possible when the API provides the total number of items,
        offset and limit in the cursor.
        """
        def _get_type_value(t: Any) -> str:
            match t:
                case str():
                    return t
                case RemoteResource():
                    return t.type
                case _:
                    return "item"

        collection_type = _get_type_value(self.type)
        item_type = _get_type_value(kind)
        # noinspection PyTypeChecker
        cursors = list(cursor.iter_pages)
        if not cursors:
            return (), cursor

        async def _request(page: IterablePageCursor) -> JSON:  # thin wrapper for formatting a log message
            log_message = None
            if isinstance(page, IndexCursor):
                log_message = f"{page.offset:>6}/{page.total:<6} {item_type.rstrip("s")}s"

            return await self._handler.get(page.url, log_message=log_message)

        responses: list[JSON] = await self.logger.get_asynchronous_iterator(
            map(_request, cursors),
            initial=0,
            total=len(cursors),
            desc=f"Extending {collection_type}",
            unit="pages",
            disable=len(cursors) < self._bar_threshold,
        )

        cursors = cursor.sort_responses(responses, path=path)
        items: list[RT] = [
            self.__class__.create_model(item, kind=kind)
            for response in responses
            for item in self._get_items_from_response(response=response, path=path)
        ]

        return tuple(items), cursors[-1]

    @classmethod
    def _get_items_from_response(cls, response: JSON, path: str | AliasPath) -> list[JSON]:
        match path:
            case str() as p:
                sub_items = response[p]
            case AliasPath() as p:
                sub_items = p.search_dict_for_path(response)
                if sub_items is PydanticUndefined:
                    sub_items = cls._get_items_from_response_nested(response, p)

        return sub_items

    @classmethod
    def _get_items_from_response_nested(cls, response: JSON, path: str | AliasPath) -> list[JSON]:
        path = path if isinstance(path, AliasPath) else AliasPath(path)

        keys = iter(path.path)
        for key in keys:
            if key == "*":
                path = AliasPath(*copy(keys))
                response = [cls._get_items_from_response_nested(it, path) for it in response]
                break

            response = response[key]

        if isinstance(response, Sequence) and all(isinstance(it, list) for it in response):  # flatten
            response = list(itertools.chain.from_iterable(response))
        return response


class ReadItemEndpoints[UT: URI, RT: RemoteResource](Endpoints[UT, RT]):
    # WORKAROUND: Replace decorator with validate_call when this issue is resolved:
    # https://github.com/pydantic/pydantic/issues/7796
    @_ApiURLSchema.validate_call
    async def get(self, url: ApiURL[UT, RT]) -> RT:
        """
        Get a resource from the API using the given ID, URL, URI, or resource.

        The URL given must relate to the resource type handled by this API model, and can be one of the following:
            * A URL (as a string or yarl.URL) pointing to the resource's API
            * A URI (as a string or URI object) for the resource
            * A resource object with a URI property for the resource
            * An ID (as a string) for the resource
        """
        response = await self._handler.get(url)
        return self.__class__.create_model(response)


class ReadItemsEndpoints[UT: URI, RT: RemoteResource](Endpoints[UT, RT]):
    _many_url: ClassVar[URL] = PrivateAttr(
        # description="The API endpoint to get multiple resources of this type in one call.",
    )
    _many_limit: ClassVar[PositiveInt] = PrivateAttr(
        # description="The maximum number of items that can be sent in each request.",
    )
    _many_path: ClassVar[str | AliasPath] = PrivateAttr(
        # description="The path to the list of items in the API response. Use "*" for wildcard matching.",
    )

    # WORKAROUND: Replace decorator with validate_call when this issue is resolved:
    # https://github.com/pydantic/pydantic/issues/7796
    @_ApiURISchema.validate_call
    async def get_many(self, uris: ApiURISequence[UT, RT], limit: PositiveInt = None) -> list[RT]:
        """
        Get multiple resources from the API using the given URIs.

        The URIs must relate to the resource type handled by this API model, and can be one of the following:
            * URLs (as strings or URL objects) pointing to the resource's API
            * URIs (as strings or URI objects)
            * Resource objects with a URI property for the resources
            * IDs (as strings) for the resources

        :param uris: A list of URIs. See above for accepted formats.
        :param limit: The number of URIs to send in each request to the API.
        """
        if limit is None:
            limit = self._many_limit

        items = []
        for batch in self._batch_items(uris, limit):
            url = self._generate_batch_url(self._many_url, batch)
            response = await self._handler.get(url)
            response_items = self._get_items_from_response(response=response, path=self._many_path)
            items.extend(map(self.__class__.create_model, response_items))

        return items


class ReadCollectionEndpoints[UT: URI, RT: RemoteCollection](Endpoints[UT, RT]):
    _extend_path: ClassVar[str | AliasPath] = PrivateAttr(
        # description="The path to the list of items in the API response. Use "*" for wildcard matching.",
    )
    _extend_type: ClassVar[str | RemoteResource] = PrivateAttr(
        # description="The type of the items in the collection."
    )

    @validate_call
    async def get_all(self, collection: PageCursor | HasPageCursor | RT) -> list[RT]:
        """Get all items in the collection by paginating through its cursor. May also give a cursor directly."""
        match collection:
            case PageCursor():
                cursor = collection
            case RemoteCollection() as collection:
                cursor = collection.cursor
                if not collection.has_all_items and isinstance(cursor, IndexCursor):
                    # minus limit so that the 'next' page requested has the offset equal to the current count
                    cursor.reset(offset=collection.count - cursor.limit)
            case HasPageCursor() as collection:
                cursor = collection.cursor
            case _:
                raise MusifyTypeError("Expected a collection or page cursor.")

        # noinspection PyArgumentList
        items, cursor = await self._get_all_items(cursor=cursor, path=self._extend_path, kind=self._extend_type)
        if isinstance(collection, RemoteCollection):
            items = itertools.chain.from_iterable((collection.iter_items, items))
            collection.cursor = cursor

        return list(items)


class WriteCollectionEndpoints[UT: URI, RT: RemoteResource](
    ReadItemEndpoints[UT, RT], ReadCollectionEndpoints[UT, RT],
):
    _batch_limit: ClassVar[PositiveInt] = PrivateAttr(
        # description="The maximum number of items that can be sent in each request to add items to the resource.",
    )

    # WORKAROUND: Replace decorator with validate_call when this issue is resolved:
    # https://github.com/pydantic/pydantic/issues/7796
    @_ApiURLSchema.validate_call
    @_ApiURISchema.validate_call
    async def append(self, url: ApiURL[UT, RT], uris: ApiURISequence[UT, RT], limit: PositiveInt = None) -> int:
        """Add items to the current user's saved items for this endpoint resource type."""
        if limit is None:
            limit = self._batch_limit

        for batch in self._batch_items(uris, limit):
            body = self._generate_append_batch_body(batch)
            await self._handler.post(url, json=body)

        return len(uris)

    @staticmethod
    def _generate_append_batch_body(values: Iterable[str]) -> JSON:
        """Generate a request body for the API endpoint for append batched requests."""
        return {"uris": list(map(str, values))}

    # WORKAROUND: Replace decorator with validate_call when this issue is resolved:
    # https://github.com/pydantic/pydantic/issues/7796
    @_ApiURLSchema.validate_call
    @_ApiURISchema.validate_call
    async def append_and_skip_duplicates(
            self, url: ApiURL[UT, RT], uris: ApiURISequence[UT, RT], limit: PositiveInt = None
    ) -> int:
        """Add items to the playlist and avoid adding any duplicates."""
        # noinspection PyArgumentList
        collection = await self.get(url)
        # noinspection PyArgumentList
        items = await self.get_all(collection)

        uris_unique = []
        uris_current = {item.uri for item in items}
        for uri in uris:
            if uri not in uris_unique and uri not in uris_current:
                uris_unique.append(uri)

        # noinspection PyArgumentList
        return await self.append(url, uris_unique, limit=limit)

    # WORKAROUND: Replace decorator with validate_call when this issue is resolved:
    # https://github.com/pydantic/pydantic/issues/7796
    @_ApiURLSchema.validate_call
    @_ApiURISchema.validate_call
    async def remove(self, url: ApiURL[UT, RT], uris: ApiURISequence[UT, RT], limit: PositiveInt = None) -> int:
        """Remove items from the current user's saved items for this endpoint resource type."""
        if limit is None:
            limit = self._batch_limit

        for batch in self._batch_items(uris, limit):
            body = self._generate_remove_batch_body(batch)
            await self._handler.delete(url, json=body)

        return len(uris)

    @staticmethod
    def _generate_remove_batch_body(values: Iterable[str]) -> JSON:
        """Generate a request body for the API endpoint for remove batched requests."""
        return {"uris": list(map(str, values))}


class ReadSavedEndpoints[UT: URI, RT: RemoteResource](Endpoints[UT, RT]):
    _saved_read_url: ClassVar[URL] = PrivateAttr(
        # description="The API endpoint to get the current user's saved items.",
    )
    _saved_limit: ClassVar[PositiveInt] = PrivateAttr(
        # description="The maximum number of items that can be sent in each request for saved items.",
    )
    _saved_path: ClassVar[str | AliasPath] = PrivateAttr(
        # description="The path to the list of saved items in the API response. Use "*" for wildcard matching.",
    )

    @validate_call
    async def get_all(self, limit: PositiveInt | None = None) -> list[RT]:
        """Get the current user's saved items for this endpoint resource type."""
        if limit is None:
            limit = self._saved_limit

        # we don't know what type of pagination will be used for saved items
        # just get a cursor which returns a url to begin pagination and figure it out later
        adapter = TypeAdapter(InitialCursor.annotation)
        cursor = adapter.validate_python(dict(url=self._saved_read_url, limit=limit))

        # noinspection PyArgumentList
        items, *_ = await self._get_all_items(cursor=cursor, path=self._saved_path, kind=self.type)
        return list(items)


class WriteSavedEndpoints[UT: URI, RT: RemoteResource](Endpoints[UT, RT]):
    _saved_write_url: ClassVar[URL] = PrivateAttr(
        # description="The API endpoint to modify the current user's saved items.",
    )
    _batch_limit: ClassVar[PositiveInt] = PrivateAttr(
        # description="The maximum number of items that can be sent in each request to add items to the resource.",
    )

    # WORKAROUND: Replace decorator with validate_call when this issue is resolved:
    # https://github.com/pydantic/pydantic/issues/7796
    @_ApiURISchema.validate_call
    async def add_many(self, uris: ApiURISequence[UT, RT], limit: PositiveInt = None) -> int:
        """Add items to the current user's saved items for this endpoint resource type."""
        if limit is None:
            limit = self._batch_limit

        for batch in self._batch_items(uris, limit):
            body = self._generate_add_batch_body(batch)
            await self._handler.put(self._saved_write_url, json=body)

        return len(uris)

    @staticmethod
    def _generate_add_batch_body(values: Iterable[str]) -> JSON:
        """Generate a request body for the API endpoint for batched requests."""
        return {"ids": list(map(str, values))}

    # WORKAROUND: Replace decorator with validate_call when this issue is resolved:
    # https://github.com/pydantic/pydantic/issues/7796
    @_ApiURISchema.validate_call
    async def remove_many(self, uris: ApiURISequence[UT, RT], limit: PositiveInt = None) -> int:
        """Remote items from the current user's saved items for this endpoint resource type."""
        if limit is None:
            limit = self._batch_limit

        for batch in self._batch_items(uris, limit):
            body = self._generate_remove_batch_body(batch)
            await self._handler.delete(self._saved_write_url, json=body)

        return len(uris)

    @staticmethod
    def _generate_remove_batch_body(values: Iterable[str]) -> JSON:
        """Generate a request body for the API endpoint for batched requests."""
        return {"ids": list(map(str, values))}


class HasEndpoints(RemoteModel):
    pass


class HasSavedEndpoints[ET: ReadSavedEndpoints | WriteSavedEndpoints](HasEndpoints):
    saved: ET = Field(
        description="Access endpoints for the current user's saved items.",
    )
