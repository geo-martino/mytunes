import itertools
from collections.abc import Iterable, Sequence, Mapping, Iterator, Collection
from contextlib import suppress, AbstractAsyncContextManager
from copy import copy
from io import BytesIO
from itertools import batched
from types import UnionType
from typing import Any, ClassVar, Self, cast, overload, get_args, get_origin

from PIL import Image, ImageFile as PILImageFile
from aiorequestful.auth import Authoriser
from aiorequestful.cache.backend.base import ResponseRepository
from aiorequestful.cache.exception import CacheError
from aiorequestful.cache.session import CachedSession
from aiorequestful.request import RequestHandler
from pydantic import InstanceOf, AliasPath, PositiveInt, validate_call, TypeAdapter, \
    PrivateAttr, model_validator, ModelWrapValidatorHandler, AliasChoices
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import PydanticUndefined
from yarl import URL

from mytunes._types import get_generic, get_generics, get_generic_type, get_bases
from mytunes.core.api.types import ApiURL, ApiURLSchema, ApiURISchema, ApiURISequence
from mytunes.core.cursors import PageCursor, HasPageCursor, IterablePageCursor, IndexCursor, InitialCursor
from mytunes.core.properties.image import ImageSource, PILImageFileT, ImageURL
from mytunes.core.properties.logger import HasLogger, HasProgress
from mytunes.core.properties.uri import URI, HasURI
from mytunes.core.remote import RemoteModel, RemoteResource
from mytunes.exception import MyTunesTypeError, MyTunesValidationError, ModelError, RequestError, APIModelError, \
    CursorResponseError
from mytunes.logger import Logger
from .._collection import RemoteCollection
from .._context import RemoteModelContext
from ..._base import BaseModel
from ..._base import ModelMetaclass
from ..._base.resource import ResourceModel


class EndpointsMetaclass(ModelMetaclass):
    def type_name(cls) -> str:
        """The name of the type of resource handled by this Endpoint type."""
        kls = cast('type[Endpoints]', cls)
        kls = get_generic(kls, expected=RemoteResource, base=Endpoints)
        if get_origin(kls) is UnionType:
            return Logger.format_list_to_string((arg.type for arg in get_args(kls)))
        return kls.type

    def item_type_name(cls) -> str | None:
        """The name for the type of items in the collection resource handled by this Endpoint type if applicable."""
        if not issubclass(cls, (CollectionReadEndpoints, CollectionWriteEndpoints)):
            return None

        kls = cast('type[Endpoints]', cls)
        with suppress(MyTunesTypeError):
            kls = get_generic(kls, expected=RemoteResource, not_expected=RemoteCollection, base=Endpoints)
            if get_origin(kls) is UnionType:
                return Logger.format_list_to_string((arg.type for arg in get_args(kls)))
            return kls.type
        return None

    def type_adapter(cls) -> TypeAdapter[RemoteResource]:
        """The type adapter for the resources handled by this Endpoint type."""
        kls = cast('type[Endpoints]', cls)
        kls = get_generic(kls, expected=RemoteResource, base=Endpoints)
        if get_origin(kls) is UnionType:
            return TypeAdapter(kls)
        return TypeAdapter(kls.annotation)

    def item_type_adapter(cls) -> TypeAdapter[RemoteResource]:
        """The type adapter to use for items in the collection resource handled by this Endpoint type if applicable."""
        kls = cast('type[Endpoints]', cls)
        bases = get_bases(kls, Endpoints)
        while issubclass(base := next(bases, None), Endpoints):
            generics = get_generics(base)

            with suppress(MyTunesTypeError):
                kls = get_generic_type(generics, expected=RemoteResource, not_expected=RemoteCollection)
                break

        if get_origin(kls) is UnionType:
            return TypeAdapter(kls)
        return TypeAdapter(kls.annotation)

    def __new__(mcs, cls_name: str, bases: tuple[type[Any], ...], namespace: dict[str, Any], **kwargs: Any):
        cls = cast('type[Endpoints]', super().__new__(mcs, cls_name, bases, namespace, **kwargs))

        if cls.__final__:
            try:
                get_generic(cls, expected=RemoteResource, base=Endpoints)
            except MyTunesTypeError:
                raise ModelError(f"Must define valid generic types for {cls_name!r}")

        if cls.__final__:
            cls._validate_generic_types()

        with suppress(NameError, TypeError, StopIteration):
            cls.type_name = mcs.type_name(cls)
            cls.type_adapter = mcs.type_adapter(cls)
            cls.item_type_name = mcs.item_type_name(cls)
            cls.item_type_adapter = mcs.item_type_adapter(cls)

        return cls

    def _validate_generic_types(cls) -> None:
        kls = cast('type[Endpoints]', cls)

        resource_kls = get_generic(kls, expected=RemoteResource, base=Endpoints)
        if len(get_generics(kls)) > 2 and issubclass(resource_kls, RemoteCollection):
            item_kls = get_generic(kls, expected=RemoteResource, not_expected=RemoteCollection, base=Endpoints)
            if not issubclass(kls, RemoteResource) or issubclass(item_kls, RemoteCollection):
                raise ModelError(f"Must define collection item types for {cls.__name__!r}")

    # TODO: migrate this to aiorequestful v2?
    def create_model[T: RemoteResource](
            cls, value: Any, context: RemoteModelContext, adapter: type[T] | TypeAdapter[T] = None,
    ) -> T:
        """Create an instance of the resource type handled by this API model from the given value."""
        kls = cast('type[Endpoints]', cls)
        if not kls.__final__:
            raise APIModelError("Can only create resources from final API models.")

        if adapter is None:
            adapter = cls.type_adapter

        match adapter:
            case TypeAdapter():
                return adapter.validate_python(value, context=context)
            case type() as t if issubclass(t, RemoteResource):
                return t.model_validate(value, context=context)

        raise APIModelError(f"Adapter type not recognised: {adapter!r}")


def _map_handler[T: RequestHandler[Authoriser, JsonSchemaValue]](
        kls: type[BaseModel], value: T | Mapping[str, T]
) -> T | dict[str, T] | dict[str, dict[str, T]]:
    key = "handler"
    match value:
        case RequestHandler():
            handler = value
        case Mapping() if set(value.keys()) == {key}:
            return _map_handler(kls, value[key])
        case _:
            return value

    return {key: handler} | {
        name: {key: handler} for name, info in kls.model_fields.items()
        if isinstance(info.annotation, type) and issubclass(info.annotation, Endpoints)
    }


type _URL_TYPE[UT, RT] = str | UT | RT
type _URI_TYPE[RT] = str | URL | RT


class Endpoints[UT: URI, RT: RemoteResource](RemoteModel, HasLogger, HasProgress, metaclass=EndpointsMetaclass):
    # TODO: drop this on aiorequestful v2
    _id_path: ClassVar[str | AliasPath | AliasChoices] = PrivateAttr(
        # description="The path to the ID of an item in the API response.",
    )
    _url_path: ClassVar[str | AliasPath | AliasChoices] = PrivateAttr(
        # description="The path to the href of an item in the API response.",
    )

    _handler: InstanceOf[RequestHandler[Authoriser, JsonSchemaValue]] = PrivateAttr(
        # description="The handler for the API endpoint.",
        default=None,
    )
    _user: RT | None = PrivateAttr(
        # description="The currently authenticated user.",
        default=None
    )

    @model_validator(mode="wrap")
    @classmethod
    def _from_handler[T](cls, value: T | RequestHandler, handler: ModelWrapValidatorHandler[Self]) -> Self:
        data = _map_handler(cls, value)

        self = handler(data)
        if isinstance(data, Mapping) and (key := "handler") in data:
            self._handler = data[key]

        return self

    @property
    def _nested_endpoints(self) -> list[Endpoints]:
        return [
            endpoints for name in type(self).model_fields.keys()
            if isinstance(endpoints := getattr(self, name), Endpoints)
        ]

    @property
    def user(self) -> RT | None:
        """The currently authenticated user, if available."""
        return self._user

    @user.setter
    def user(self, value: RT | None) -> None:
        self._user = value

        # set for all other nested endpoints
        for endpoints in self._nested_endpoints:
            endpoints.user = value

    @property
    def _model_context(self) -> RemoteModelContext:
        # WORKAROUND: keeps throwing AttributeError if accessed through the class
        model_type = type(self).type_name
        return RemoteModelContext(user=self.user, type=model_type)

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        if self._handler.closed:
            await self._handler.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if not self._handler.closed:
            await self._handler.__aexit__(exc_type, exc_val, exc_tb)
        return await super().__aexit__(exc_type, exc_val, exc_tb)

    @staticmethod
    def _batch_values(values: Iterable, limit: int) -> batched:
        """Batch the given values into sublists of the given size."""
        return itertools.batched(map(str, values), limit)

    @classmethod
    def create_uri(cls, value: Any) -> URI:
        """Create a URI for the resource type handled by this API model from the given ID."""
        context = RemoteModelContext(type=cls.type_name)
        return URI.get_adapter_for_source(cls.source).validate_python(value, context=context)

    # TODO: migrate this to aiorequestful v2
    async def _get_all_items(
            self, cursor: PageCursor, path: str | AliasPath | AliasChoices, adapter: TypeAdapter | None = None,
    ) -> tuple[tuple[RT, ...], PageCursor]:
        """Get all items from a request with paginated responses using the fastest available method."""
        if cursor.next is None:
            self._handler.log("SKIP", cursor.url, message="Cursor already fully extended")
            return (), cursor

        collection_type = type(self).type_name
        item_type = type(self).item_type_name
        amount = cursor.total or "all"

        if item_type and item_type != collection_type:
            message = f"Extending {collection_type} with {amount} {item_type}s"
        else:
            message = f"Getting {amount} {item_type}s"
        self._handler.log("INFO", cursor.url, message=message)

        items, cursor = await self._get_all_items_from_cursor(cursor, path=path, adapter=adapter)

        message = f"Retrieved "
        if cursor.total:
            message += f"{len(items):>6}/{cursor.total:<6}"
        else:
            message += f"{len(items):>6}"

        message += f" {item_type}s"
        if item_type and item_type != collection_type:
            message += f" for {collection_type}"

        self._handler.log("DONE", cursor.url, message=message)

        return items, cursor

    # TODO: migrate this to aiorequestful v2
    async def _get_all_items_from_cursor(
            self, cursor: PageCursor, path: str | AliasPath | AliasChoices, adapter: TypeAdapter | None = None,
    ) -> tuple[tuple[RT, ...], PageCursor]:
        match cursor:
            case IterablePageCursor():
                return await self._get_all_items_by_generation(cursor, path=path, adapter=adapter)
            case _:
                return await self._get_all_items_by_pagination(cursor, path=path, adapter=adapter)

    # TODO: migrate this to aiorequestful v2
    async def _get_all_items_by_pagination(
            self, cursor: PageCursor, path: str | AliasPath | AliasChoices, adapter: TypeAdapter | None = None,
    ) -> tuple[tuple[RT, ...], PageCursor]:
        """
        Get all items by paginating through the cursor, which must have a next URL for the first page of items.

        This is usually the slower approach, but is more widely supported as it does not require the API
        to provide the total number of items, offset and limit in the page cursor.
        """
        items: list[RT] = []

        while cursor.next is not None:
            response = await self._get_page(cursor.next)

            response_items = self._get_items_from_response(response=response, path=path)
            await self._cache_responses(response_items)

            items.extend(
                type(self).create_model(it, context=self._model_context, adapter=adapter)
                for it in response_items
            )

            cursor = cursor.next.get_cursor_from_response(response=response, path=path)
            if cursor.next == cursor:
                raise CursorResponseError(
                    "The next cursor is the same as the current cursor, which may cause an infinite loop."
                )

            if isinstance(cursor, IterablePageCursor):
                # switch to faster generation mode for the remaining pages
                response_items, cursor = await self._get_all_items_by_generation(cursor, path=path, adapter=adapter)
                items.extend(response_items)
                break

        return tuple(items), cursor

    # TODO: migrate this to aiorequestful v2
    async def _get_all_items_by_generation[T: IterablePageCursor](
            self, cursor: T, path: str | AliasPath | AliasChoices, adapter: TypeAdapter | None = None,
    ) -> tuple[tuple[RT, ...], T]:
        """
        Get all items by generating the next cursors for the next pages of items and sending requests
        for them asynchronously.

        This is usually the faster approach, but is only possible when the API provides the total number of items,
        offset and limit in the cursor.
        """
        # noinspection PyTypeChecker
        cursors = list(cursor.iter_pages)
        if not cursors:
            return (), cursor

        collection_type = type(self).type_name
        item_type = type(self).item_type_name
        if item_type and item_type != collection_type:
            desc_type = f"{collection_type} {item_type}"
        else:
            desc_type = collection_type

        task_id = self._progress.add_task(description=f"Getting {desc_type}s", total=len(cursors))
        tasks = map(self._get_page, cursors)
        responses: list[JsonSchemaValue] = await self._run_tasks_async(tasks, task_id=task_id)

        cursors = cursor.sort_responses(responses, path=path)
        response_items = [
            item for response in responses
            for item in self._get_items_from_response(response=response, path=path)
        ]
        await self._cache_responses(response_items)

        items: list[RT] = [
            type(self).create_model(item, context=self._model_context, adapter=adapter)
            for item in response_items
        ]

        return tuple(items), cursors[-1]

    # TODO: migrate this to aiorequestful v2
    async def _get_page(self, page: PageCursor) -> JsonSchemaValue:
        """Thin wrapper for sending a get request from a page cursor while also formatting a log message"""
        log_message = None
        if isinstance(page, IndexCursor):
            item_type = type(self).item_type_name or "item"
            log_message = f"{page.offset:>6}/{page.total:<6} {item_type}s"

        return await self._handler.get(page.url, log_message=log_message)

    # TODO: migrate this to aiorequestful v2
    @classmethod
    def _get_items_from_response[T: JsonSchemaValue](
            cls, response: T, path: str | AliasPath | AliasChoices
    ) -> list[T]:
        items = None
        log = path

        match path:
            case str() as key if key in response:
                items = response[key]
                log = key

            case AliasPath() as alias:
                items = alias.search_dict_for_path(response)
                if items is PydanticUndefined:
                    items = cls._get_items_from_response_nested(response, alias)
                log = ".".join(alias.path)

            case AliasChoices() as choices:
                log_parts = []
                for alias in choices.choices:
                    with suppress(CursorResponseError):
                        items = cls._get_items_from_response(response, path=alias)
                    log_parts.append(".".join(alias.path) if isinstance(alias, AliasPath) else alias)

                log = " | ".join(log_parts)

        if isinstance(items, list):
            return items

        raise CursorResponseError(f"Could not find items in response using the given path/s: {log}")

    # TODO: migrate this to aiorequestful v2
    @classmethod
    def _get_items_from_response_nested[T: JsonSchemaValue](
            cls, response: T, path: str | AliasPath
    ) -> list[T] | None:
        path = path if isinstance(path, AliasPath) else AliasPath(path)

        keys = iter(path.path)
        for key in keys:
            if key == "*":
                path = AliasPath(*copy(keys))
                response = [cls._get_items_from_response_nested(it, path) for it in response]
                break

            if key not in response:
                return

            response = response[key]

        if isinstance(response, Sequence) and all(isinstance(it, list) for it in response):  # flatten
            response = list(itertools.chain.from_iterable(response))
        return response

    # TODO: migrate this to aiorequestful v2
    def _get_cache_repository(self, url: URL | Sequence[URL]) -> ResponseRepository | None:
        session = self._handler.session
        if not isinstance(session, CachedSession):
            self._handler.log("CACHE", url, message="Cache not configured, skipping...")
            return

        repository = session.cache.get_repository_from_url(url=url)
        if repository is None:
            self._handler.log("CACHE", url, message="No repository for this endpoint, skipping...")
            return

        return repository

    # TODO: migrate this to aiorequestful v2
    async def _get_responses_from_cache[T: str](
            self, url: URL, values: Collection[T]
    ) -> dict[str, JsonSchemaValue | None]:
        """
        Attempt to find the given ``values`` in the cache of the request handler and return results.

        :param url: The base API URL endpoint for the required requests.
        :param values: List of IDs to append to the given URL.
        :return: Map of ID to its cached result if found, None otherwise.
        """
        if (repository := self._get_cache_repository(url)) is None:
            return {value: None for value in values}

        async def _get_response(value: T) -> tuple[T, JsonSchemaValue | None]:
            return value, await repository.get_response(("GET", value))

        results = dict(await self._run_tasks_async(map(_get_response, values)))

        retrieved_count = sum(result is not None for result in results.values())
        messages = [
            f"Retrieved {retrieved_count:>6} cached responses",
            f"{len(results) - retrieved_count:>6} not found in cache"
        ]
        self._handler.log(method="CACHE", url=url, messages=messages)

        return results

    # TODO: migrate this to aiorequestful v2
    async def _cache_responses(self, responses: Collection[JsonSchemaValue]) -> None:
        """Persist ``responses`` for a given ``url`` to the cache."""
        urls = set()
        for response in responses:
            url = self._get_value_from_response(response, self._url_path)
            if url is None:
                continue

            url = url.replace(self._get_value_from_response(response, self._id_path), "")
            urls.add(url)

        if not urls:
            return
        if len(urls) != 1:
            raise CacheError(
                "Too many different types of results given. Given results must relate to the same repository type."
            )

        url = urls.pop()
        if (repository := self._get_cache_repository(url)) is None:
            return

        responses_map = {}
        for response in responses:
            id_value = self._get_value_from_response(response, path=self._id_path)
            if id_value is None:
                continue

            responses_map[("GET", id_value)] = response

        message = f"Caching {len(responses_map)} responses to {repository.settings.name!r} repository"
        self._handler.log(method="CACHE", url=url, message=message)
        await repository.save_responses(responses_map)

    # TODO: migrate this to aiorequestful v2
    @classmethod
    def _get_value_from_response(cls, response: JsonSchemaValue, path: str | AliasPath | AliasChoices) -> Any | None:
        match path:
            case str() as key:
                return response.get(key)

            case AliasPath() as alias:
                return alias.search_dict_for_path(response)

            case AliasChoices() as choices:
                choices = iter(choices.choices)
                value = None
                while (choice := next(choices, None)) is not None and value is not None:
                    value = cls._get_value_from_response(response, path=choice)

                return value

    # TODO: migrate this to aiorequestful v2
    @staticmethod
    def _get_type_value(t: Any) -> str:
        match t:
            case str():
                return t.rstrip("s")
            case ResourceModel():
                return t.type.rstrip("s")
            case _ if isinstance(t, type) and issubclass(t, ResourceModel):
                return t.type.rstrip("s")
            case _:
                return "item"

    async def _get_image_data(self, image: bytes | ImageSource | PILImageFileT) -> tuple[bytes, str]:
        data = None

        match image:
            case ImageURL() as img:
                img = await img.load(self._handler.session)
            case ImageSource() as img:
                img = await img.load()
            case PILImageFile.ImageFile() as img:
                img = img
            case bytes() as value:
                data = value
                img = Image.open(BytesIO(data))
            case _:
                raise RequestError("Unknown image format.")

        mime = Image.MIME[img.format]
        if data is None:
            data = BytesIO()
            img.save(data, format=img.format)
            data = data.getvalue()

        return data, mime


class ItemReadEndpoints[UT: URI, RT: RemoteResource](Endpoints[UT, RT]):
    @overload
    async def get(self, url: _URL_TYPE[UT, RT]) -> RT: ...

    @overload
    async def get(self, url: URL) -> RT: ...

    @ApiURLSchema.validate_call()  # WORKAROUND: replace with @validate_call when supported
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
        return type(self).create_model(response, context=self._model_context)


class CollectionReadEndpoints[UT: URI, RT: RemoteCollection, IT: RemoteResource](Endpoints[UT, RT]):
    _extend_path: ClassVar[str | AliasPath | AliasChoices] = PrivateAttr(
        # description="The path to the list of items in the API response. Use '*' for wildcard matching.",
    )

    @validate_call
    async def get_all(self, collection: PageCursor | HasPageCursor | RT) -> list[IT]:
        """Get all items in the collection by paginating through its cursor. May also give a cursor directly."""
        match collection:
            case PageCursor():
                cursor = collection
            case RemoteCollection() as collection:
                cursor = collection.cursor
                if not collection.has_all_items and isinstance(cursor, IndexCursor):
                    # minus limit so that the 'next' page requested has the offset equal to the current count
                    cursor.reset(offset=collection.total - cursor.limit)
            case HasPageCursor() as collection:
                cursor = collection.cursor
            case _:
                raise RequestError("Expected a collection or page cursor.")

        adapter = type(self).item_type_adapter
        items, cursor = await self._get_all_items(cursor, path=self._extend_path, adapter=adapter)

        if isinstance(collection, RemoteCollection):
            items = itertools.chain.from_iterable((collection.items, items))
            collection.__dict__["cursor"] = cursor

        return list(items)


class CollectionWriteEndpoints[UT: URI, RT: RemoteResource, IT: HasURI](Endpoints[UT, RT]):
    _write_limit: ClassVar[PositiveInt] = PrivateAttr(
        # description="The maximum number of items that can be sent in each request for writing items.",
    )

    @overload
    async def add(
            self, url: _URL_TYPE[UT, RT], uris: Sequence[_URI_TYPE[RT]], limit: PositiveInt | None = None,
    ) -> int: ...

    @overload
    async def add(self, url: URL, uris: Sequence[UT], limit: PositiveInt | None = None) -> int: ...

    @ApiURLSchema.validate_call()  # WORKAROUND: replace with @validate_call when supported
    @ApiURISchema.validate_call("uris", is_sequence=True)
    async def add(
            self, url: ApiURL[UT, RT], uris: ApiURISequence[UT, IT], limit: PositiveInt | None = None,
    ) -> int:
        """Add items to the current user's library items for this endpoint resource type."""
        collection_type = type(self).type_name
        item_type = type(self).item_type_name or "item"

        if not uris:
            self._handler.log("SKIP", url, message=f"No {item_type}s given to add")
            return 0

        if limit is None:
            limit = self._write_limit

        async def _post_items(batch: Collection) -> None:
            message = f"Adding {len(batch):>6} {item_type}s to {collection_type}"
            kwargs = self._generate_add_collection_kwargs(batch)
            await self._handler.post(url, log_message=message, **kwargs)

        batches = list(self._batch_values(uris, limit))
        task_id = self._progress.add_task(
            description=f"Adding {item_type}s to {collection_type}", total=len(batches),
        )
        await self._run_tasks_async(map(_post_items, batches), task_id=task_id)

        self._handler.log("DONE", url, message=f"Added {len(uris):>6} {item_type}s to {collection_type}")
        return len(uris)

    @staticmethod
    def _generate_add_collection_kwargs(values: Iterable[str]) -> dict[str, JsonSchemaValue]:
        """Generate request kwargs for the API endpoint for append batched requests."""
        return {"json": {"ids": list(map(str, values))}}

    @overload
    async def remove(
            self, url: _URL_TYPE[UT, RT], uris: Sequence[_URI_TYPE[RT]], limit: PositiveInt | None = None,
    ) -> int: ...

    @overload
    async def remove(self, url: URL, uris: Sequence[UT], limit: PositiveInt | None = None) -> int: ...

    @ApiURLSchema.validate_call()  # WORKAROUND: replace with @validate_call when supported
    @ApiURISchema.validate_call("uris", is_sequence=True)
    async def remove(
            self, url: ApiURL[UT, RT], uris: ApiURISequence[UT, IT], limit: PositiveInt | None = None,
    ) -> int:
        """Remove items from the current user's library items for this endpoint resource type."""
        collection_type = type(self).type_name
        item_type = type(self).item_type_name or "item"

        if not uris:
            self._handler.log("SKIP", url, message=f"No {item_type}s given to remove")
            return 0

        if limit is None:
            limit = self._write_limit

        async def _delete_items(batch: Collection) -> None:
            message = f"Removing {len(batch):>6} {item_type}s from {collection_type}"
            kwargs = self._generate_remove_collection_kwargs(batch)
            await self._handler.delete(url, log_message=message, **kwargs)

        batches = list(self._batch_values(uris, limit))
        task_id = self._progress.add_task(
            description=f"Removing {item_type}s from {collection_type}", total=len(batches),
        )
        await self._run_tasks_async(map(_delete_items, batches), task_id=task_id)

        self._handler.log("DONE", url, message=f"Removed {len(uris):>6} {item_type}s from {collection_type}")
        return len(uris)

    @staticmethod
    def _generate_remove_collection_kwargs(values: Iterable[str]) -> dict[str, JsonSchemaValue]:
        """Generate a request body for the API endpoint for remove batched requests."""
        return {"json": {"ids": list(map(str, values))}}


class BatchReadEndpoints[UT: URI, RT: RemoteResource](Endpoints[UT, RT]):
    _read_url: ClassVar[URL] = PrivateAttr(
        # description="The API endpoint to get multiple resources of this type in one call.",
    )
    _read_limit: ClassVar[PositiveInt] = PrivateAttr(
        # description="The maximum number of items that can be sent in each request.",
    )
    _read_path: ClassVar[str | AliasPath | AliasChoices] = PrivateAttr(
        # description="The path to the list of items in the API response. Use '*' for wildcard matching.",
    )

    @overload
    async def get_many(self, uris: Sequence[_URI_TYPE[RT]], limit: PositiveInt | None = None) -> int: ...

    @overload
    async def get_many(self, uris: Sequence[UT], limit: PositiveInt | None = None) -> int: ...

    @ApiURISchema.validate_call("uris", is_sequence=True)  # WORKAROUND: replace with @validate_call when supported
    async def get_many(self, uris: ApiURISequence[UT, RT], limit: PositiveInt | None = None) -> list[RT]:
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
        item_type = type(self).item_type_name or "item"

        if not uris:
            self._handler.log("SKIP", self._read_url, message=f"No {item_type}s given to add")
            return []

        if limit is None:
            limit = self._read_limit

        # TODO: drop this on aiorequestful v2
        cache_responses = await self._get_responses_from_cache(self._read_url, uris)
        cache_items = [
            type(self).create_model(response, context=self._model_context)
            for response in cache_responses.values() if response is not None
        ]
        uncached_uris = [uri for uri, response in cache_responses.items() if response is None]

        async def _get_items(batch: Collection) -> Iterator[RT]:
            url = self._generate_batch_url(self._read_url, batch)
            message = f"Getting {len(batch):>6} {item_type}s"
            response = await self._handler.get(url, log_message=message)

            response_items = self._get_items_from_response(response=response, path=self._read_path)
            return (type(self).create_model(it, context=self._model_context) for it in response_items)

        batches = list(self._batch_values(uncached_uris, limit))
        task_id = self._progress.add_task(description=f"Getting {item_type}s", total=len(batches))
        responses = await self._run_tasks_async(map(_get_items, batches), task_id=task_id)

        # TODO: amend this on aiorequestful v2
        items = cache_items + [item for batch in responses for item in batch]
        items.sort(key=lambda it: uris.index(it.uri.id))

        return items

    @classmethod
    def _generate_batch_url(cls, base_url: URL, values: Iterable) -> URL:
        """Generate a URL for the API endpoint for batched requests."""
        return base_url.update_query(ids=",".join(map(str, values)))


_INITIAL_CURSOR_ADAPTER = TypeAdapter[InitialCursor](InitialCursor.annotation)


class BatchReadAllEndpoints[UT: URI, RT: RemoteResource](Endpoints[UT, RT]):
    _read_all_url: ClassVar[URL] = PrivateAttr(
        # description="The API endpoint to get the current user's library items.",
    )
    _read_all_limit: ClassVar[PositiveInt] = PrivateAttr(
        # description="The maximum number of items that can be sent in each request for reading library items.",
    )
    _read_all_path: ClassVar[str | AliasPath | AliasChoices] = PrivateAttr(
        # description="The path to the list of library items in the API response. Use '*' for wildcard matching.",
    )

    @validate_call
    async def get_all(self, limit: PositiveInt | None = None) -> list[RT]:
        """Get the current user's library items for this endpoint resource type."""
        if limit is None:
            limit = self._read_all_limit

        # we don't know what type of pagination will be used for library items
        # just get a cursor which returns a url to begin pagination and figure it out later
        cursor = InitialCursor.from_url(url=self._read_all_url, source=self.source, limit=limit)

        items, *_ = await self._get_all_items(cursor, path=self._read_all_path)
        return list(items)


class BatchWriteEndpoints[UT: URI, RT: RemoteResource](Endpoints[UT, RT]):
    _write_url: ClassVar[URL] = PrivateAttr(
        # description="The API endpoint to modify the current user's library items.",
    )
    _write_limit: ClassVar[PositiveInt] = PrivateAttr(
        # description="The maximum number of items that can be sent in each request for writing library items.",
    )

    @overload
    async def add_many(self, uris: Sequence[_URI_TYPE[RT]], limit: PositiveInt | None = None) -> int: ...

    @overload
    async def add_many(self, uris: Sequence[UT], limit: PositiveInt | None = None) -> int: ...

    @ApiURISchema.validate_call("uris", is_sequence=True)  # WORKAROUND: replace with @validate_call when supported
    async def add_many(self, uris: ApiURISequence[UT, RT], limit: PositiveInt | None = None) -> int:
        """Add items in batches for this endpoint resource type."""
        item_type = type(self).item_type_name or "item"

        if not uris:
            self._handler.log("SKIP", self._write_url, message=f"No {item_type}s given to add")
            return 0

        if limit is None:
            limit = self._write_limit

        async def _post_items(batch: Collection) -> None:
            message = f"Adding {len(batch):>6} {item_type}s"
            kwargs = self._generate_add_batch_kwargs(batch)
            await self._handler.put(self._write_url, log_message=message, **kwargs)

        batches = list(self._batch_values(uris, limit))
        task_id = self._progress.add_task(description=f"Adding {item_type}s", total=len(batches))
        await self._run_tasks_async(map(_post_items, batches), task_id=task_id)

        self._handler.log("DONE", self._write_url, message=f"Added {len(uris):>6} {item_type}s")
        return len(uris)

    @staticmethod
    def _generate_add_batch_kwargs(values: Iterable[Any]) -> dict[str, JsonSchemaValue]:
        """Generate a request body for the API endpoint for batched requests."""
        return {"json": {"ids": list(map(str, values))}}

    @overload
    async def remove_many(self, uris: Sequence[_URI_TYPE[RT]], limit: PositiveInt | None = None) -> int: ...

    @overload
    async def remove_many(self, uris: Sequence[UT], limit: PositiveInt | None = None) -> int: ...

    @ApiURISchema.validate_call("uris", is_sequence=True)  # WORKAROUND: replace with @validate_call when supported
    async def remove_many(self, uris: ApiURISequence[UT, RT], limit: PositiveInt | None = None) -> int:
        """Remote items in batches for this endpoint resource type."""
        item_type = type(self).item_type_name or "item"

        if not uris:
            self._handler.log("SKIP", self._write_url, message=f"No {item_type}s given to remove")
            return 0

        if limit is None:
            limit = self._write_limit

        async def _delete_items(batch: Collection) -> None:
            message = f"Removing {len(batch):>6} {item_type}s"
            kwargs = self._generate_remove_batch_kwargs(batch)
            await self._handler.delete(self._write_url, log_message=message, **kwargs)

        batches = list(self._batch_values(uris, limit))
        task_id = self._progress.add_task(description=f"Removing {item_type}s", total=len(batches))
        await self._run_tasks_async(map(_delete_items, batches), task_id=task_id)

        self._handler.log("DONE", self._write_url, message=f"Removed {len(uris):>6} {item_type}s")
        return len(uris)

    @staticmethod
    def _generate_remove_batch_kwargs(values: Iterable[Any]) -> dict[str, JsonSchemaValue]:
        """Generate a request body for the API endpoint for batched requests."""
        return {"json": {"ids": list(map(str, values))}}


class HasEndpoints(RemoteModel, AbstractAsyncContextManager):
    @property
    def _handler(self) -> RequestHandler:
        fields = {name for name in type(self).model_fields.keys() if isinstance(getattr(self, name), Endpoints)}
        return next(getattr(self, name)._handler for name in fields)

    @model_validator(mode="wrap")
    @classmethod
    def _from_handler[T](cls, value: T | RequestHandler, handler: ModelWrapValidatorHandler[Self]) -> Self:
        data = _map_handler(cls, value)

        self = handler(data)
        if isinstance(self, Endpoints) and isinstance(data, Mapping) and (key := "handler") in data:
            self._handler = data[key]

        return self

    @model_validator(mode="after")
    def _all_handlers_are_the_same(self) -> Self:
        fields = {name for name in type(self).model_fields.keys() if isinstance(getattr(self, name), Endpoints)}
        if not fields:
            return self

        # noinspection PyProtectedMember
        handlers = {id(getattr(self, name)._handler) for name in fields}
        if len(handlers) != 1:
            raise MyTunesValidationError(
                "All endpoint models must use the same request handler for API to function correctly."
            )

        return self

    @property
    def _nested_endpoints(self) -> list[Endpoints]:
        return [
            endpoints for name in type(self).model_fields.keys()
            if isinstance(endpoints := getattr(self, name), Endpoints)
        ]

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        for endpoints in self._nested_endpoints:
            await endpoints.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        for endpoints in self._nested_endpoints:
            await endpoints.__aexit__(exc_type, exc_val, exc_tb)
        return await super().__aexit__(exc_type, exc_val, exc_tb)
