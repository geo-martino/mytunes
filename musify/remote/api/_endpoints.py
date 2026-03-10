import contextlib
import itertools
from collections.abc import Iterable, Sequence, Mapping, Iterator
from copy import copy
from itertools import batched
from typing import Any, ClassVar, Annotated, Self, Type

from aiorequestful.auth import Authoriser
from aiorequestful.request import RequestHandler
from aiorequestful.types import JSON
from pydantic import Field, InstanceOf, AliasPath, NonNegativeInt, PositiveInt, validate_call, TypeAdapter, \
    PrivateAttr, model_validator, ModelWrapValidatorHandler, ValidationError
from pydantic_core import PydanticUndefined
from yarl import URL

from musify.exception import MusifyTypeError, MusifyValueError
from musify.models._base import AttributeModelMetaclass
from musify.models.properties.logger import HasLogger
from musify.models.properties.uri import URI
from musify.models.url import HttpURL
from musify.remote import RemoteResource, RemoteModel
from musify.remote.api.types import ApiURLSchema, ApiURISchema
from musify.remote.collection import ItemsCursor, RemoteCollection


class RemoteEndpointsMetaclass(AttributeModelMetaclass):
    def create_model(cls: RemoteEndpoints, value: Any, kind: str | type = None) -> RemoteResource:
        """Create an instance of the resource type handled by this API model from the given value."""
        if not cls.__final__:
            raise MusifyTypeError("Can only create resources from final API models.")

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

        errors = []
        for kls in type_classes:
            try:
                return kls.model_validate(value)
            except ValidationError as exc:
                errors.append(exc)

        raise MusifyValueError(
            f"Could not create a {cls.source!r} resource of type {kind!r} from the given value. "
            f"Errors: \n{"\n".join(map(str, errors))}"
        )


class RemoteEndpoints[UT: URI, RT: RemoteResource](
    RemoteModel, HasLogger, metaclass=RemoteEndpointsMetaclass
):
    type: ClassVar[str | Type[RemoteResource]] = Field(
        description="The type of resources the endpoints of this API model handle.",
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
    @validate_call
    def _create_saved_items_cursor(
            url: HttpURL, limit: PositiveInt | None = None, offset: NonNegativeInt | None = None
    ) -> ItemsCursor:
        cursor_adapter = TypeAdapter(ItemsCursor.annotation)
        cursor = cursor_adapter.validate_python(url)

        # only set if given as the source's cursor may have default values set
        if limit is not None:
            cursor.limit = limit
        if offset is not None:
            cursor.offset = offset

        cursor.next = cursor.current
        return cursor

    @validate_call
    async def _get_all_items_from_cursor(
            self,
            cursor: ItemsCursor,
            path: str | AliasPath,
            kind: str | Type = None,
    ) -> tuple[Iterator[RT], ItemsCursor]:
        items: Iterator[RT] = iter(())
        while cursor.next is not None:
            response = await self._handler.get(cursor.next)
            response_items = self._get_items_from_response(response=response, path=path, kind=kind)
            items = itertools.chain(items, response_items)
            cursor = self._get_cursor_from_response(response=response, path=path, cursor=cursor)

        return items, cursor

    @classmethod
    def _get_items_from_response(
            cls,
            response: JSON,
            path: str | AliasPath,
            kind: str | Type = None,
    ) -> Iterator[RT]:
        match path:
            case str() as p:
                sub_items = response[p]
            case AliasPath() as p:
                sub_items = p.search_dict_for_path(response)
                if sub_items is PydanticUndefined:
                    sub_items = cls._get_items_from_response_nested(response, p)

        return (cls.create_model(it, kind=kind) for it in sub_items)

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

    @classmethod
    def _get_cursor_from_response[T: ItemsCursor](cls, response: JSON, path: AliasPath, cursor: T) -> T:
        match path:
            case str():
                return cursor.model_validate(response)
            case AliasPath():  # attempt to find cursor in response at path if it is not at the top level
                for key in path.path:
                    with contextlib.suppress(ValidationError):
                        return cursor.model_validate(response)
                    response = response[key]

        raise MusifyValueError("Could not find cursor in response at the given path.")

    @staticmethod
    def _batch_items(uris: Iterable, limit: int) -> batched[str]:
        """Batch the given URIs into sublists of the given size."""
        return itertools.batched(map(str, uris), limit)

    @classmethod
    def _generate_batch_url(cls, base_url: URL, values: Iterable) -> URL:
        """Generate a URL for the API endpoint for batched requests."""
        return base_url.update_query(ids=",".join(map(str, values)))


class RemoteGetSingleEndpoints[UT: URI, RT: RemoteResource](RemoteEndpoints[UT, RT]):
    # WORKAROUND: Replace decorator with validate_call when this issue is resolved:
    # https://github.com/pydantic/pydantic/issues/7796
    @ApiURLSchema.validate_call
    async def get(self, url: Annotated[URL, ApiURLSchema[UT, RT]]) -> RT:
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


class RemoteGetManyEndpoints[UT: URI, RT: RemoteResource](RemoteEndpoints[UT, RT]):
    _many_url: ClassVar[URL] = PrivateAttr(
        # description="The API endpoint to get multiple resources of this type in one call.",
    )
    _many_limit: ClassVar[PositiveInt] = PrivateAttr(
        # description="The maximum number of items that can be sent in each request.",
    )
    _many_path: ClassVar[str | AliasPath] = PrivateAttr(
        # description="The path to the list of items in the API response.",
    )

    # WORKAROUND: Replace decorator with validate_call when this issue is resolved:
    # https://github.com/pydantic/pydantic/issues/7796
    @ApiURISchema.validate_call
    async def get_many(
            self, uris: Sequence[Annotated[URI, ApiURISchema[UT, RT]]], limit: PositiveInt = None
    ) -> list[RT]:
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
            items.extend(self._get_items_from_response(response=response, path=self._many_path))

        return items


class RemoteCollectionEndpoints[UT: URI, RT: RemoteCollection](RemoteEndpoints[UT, RT]):
    _extend_path: ClassVar[str | AliasPath] = PrivateAttr(
        # description="The path to the list of items in the API response.",
    )
    _extend_type: ClassVar[str | AliasPath] = PrivateAttr(
        # description="The path to the list of items in the API response.",
    )

    @validate_call
    async def get_all(self, collection: RT | ItemsCursor) -> list[RT]:
        """Get all items in the collection by paginating through its cursor. May also give a cursor directly."""
        match collection:
            case ItemsCursor():
                cursor = collection
            case RemoteCollection() as collection:
                cursor = collection.cursor
                if not collection.has_all_items and cursor.next is None:
                    cursor.offset = collection.loaded_count  # sets the offset on the current URL
                    cursor.next = cursor.current
            case _:
                raise MusifyTypeError("Expected a collection or items cursor.")

        # noinspection PyArgumentList
        items, cursor = await self._get_all_items_from_cursor(
            cursor=cursor, path=self._extend_path, kind=self._extend_type
        )
        if isinstance(collection, RemoteCollection):
            collection.cursor = cursor

        return list(items)


class RemoteMutableCollectionEndpoints[UT: URI, RT: RemoteResource](
    RemoteGetSingleEndpoints[UT, RT], RemoteCollectionEndpoints[UT, RT],
):
    _batch_limit: ClassVar[PositiveInt] = PrivateAttr(
        # description="The maximum number of items that can be sent in each request to add items to the resource.",
    )

    # WORKAROUND: Replace decorator with validate_call when this issue is resolved:
    # https://github.com/pydantic/pydantic/issues/7796
    @ApiURLSchema.validate_call
    @ApiURISchema.validate_call
    async def append(
            self,
            url: Annotated[URL, ApiURLSchema[UT, RT]],
            uris: Sequence[Annotated[URI, ApiURISchema[UT, RT]]],
            limit: PositiveInt = None
    ) -> int:
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
    @ApiURLSchema.validate_call
    @ApiURISchema.validate_call
    async def append_and_skip_duplicates(
            self,
            url: Annotated[URL, ApiURLSchema[UT, RT]],
            uris: Sequence[Annotated[URI, ApiURISchema[UT, RT]]],
            limit: PositiveInt = None
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
    @ApiURLSchema.validate_call
    @ApiURISchema.validate_call
    async def remove(
            self,
            url: Annotated[URL, ApiURLSchema[UT, RT]],
            uris: Sequence[Annotated[URI, ApiURISchema[UT, RT]]],
            limit: PositiveInt = None
    ) -> int:
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


class RemoteGetSavedEndpoints[UT: URI, RT: RemoteResource](RemoteEndpoints[UT, RT]):
    _saved_url: ClassVar[URL] = PrivateAttr(
        # description="The API endpoint to get the current user's saved items.",
    )
    _saved_limit: ClassVar[PositiveInt] = PrivateAttr(
        # description="The maximum number of items that can be sent in each request for saved items.",
    )
    _saved_path: ClassVar[str | AliasPath] = PrivateAttr(
        # description="The path to the list of saved items in the API response.",
    )

    @validate_call
    async def get_all(self, limit: PositiveInt | None = None, offset: NonNegativeInt | None = None) -> list[RT]:
        """Get the current user's saved items for this endpoint resource type."""
        if limit is None:
            limit = self._saved_limit

        cursor = self._create_saved_items_cursor(self._saved_url, limit=limit, offset=offset)
        # noinspection PyArgumentList
        items, cursor = await self._get_all_items_from_cursor(cursor=cursor, path=self._saved_path, kind=self.type)
        return list(items)


class RemoteMutableSavedEndpoints[UT: URI, RT: RemoteResource](RemoteEndpoints[UT, RT]):
    _saved_url: ClassVar[URL] = PrivateAttr(
        # description="The API endpoint to get the current user's saved items.",
    )
    _batch_limit: ClassVar[PositiveInt] = PrivateAttr(
        # description="The maximum number of items that can be sent in each request to add items to the resource.",
    )

    # WORKAROUND: Replace decorator with validate_call when this issue is resolved:
    # https://github.com/pydantic/pydantic/issues/7796
    @ApiURISchema.validate_call
    async def add_many(
            self, uris: Sequence[Annotated[URI, ApiURISchema[UT, RT]]], limit: PositiveInt = None
    ) -> None:
        """Add items to the current user's saved items for this endpoint resource type."""
        if limit is None:
            limit = self._batch_limit

        for batch in self._batch_items(uris, limit):
            body = self._generate_add_batch_body(batch)
            await self._handler.put(self._saved_url, json=body)

    @staticmethod
    def _generate_add_batch_body(values: Iterable[str]) -> JSON:
        """Generate a request body for the API endpoint for batched requests."""
        return {"ids": list(map(str, values))}

    # WORKAROUND: Replace decorator with validate_call when this issue is resolved:
    # https://github.com/pydantic/pydantic/issues/7796
    @ApiURISchema.validate_call
    async def remove_many(
            self, uris: Sequence[Annotated[URI, ApiURISchema[UT, RT]]], limit: PositiveInt = None
    ) -> None:
        """Remote items from the current user's saved items for this endpoint resource type."""
        if limit is None:
            limit = self._batch_limit

        for batch in self._batch_items(uris, limit):
            body = self._generate_remove_batch_body(batch)
            await self._handler.delete(self._saved_url, json=body)

    @staticmethod
    def _generate_remove_batch_body(values: Iterable[str]) -> JSON:
        """Generate a request body for the API endpoint for batched requests."""
        return {"ids": list(map(str, values))}


class HasEndpoints(RemoteModel):
    pass
