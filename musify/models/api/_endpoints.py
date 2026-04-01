import functools
import itertools
from collections.abc import Iterable, Sequence, Mapping, Iterator, Collection
from contextlib import suppress
from copy import copy
from io import BytesIO
from itertools import batched
from typing import Any, ClassVar, Self, Type, Union, cast

from PIL import Image, ImageFile as PILImageFile
from aiorequestful.auth import Authoriser
from aiorequestful.cache.backend.base import ResponseRepository
from aiorequestful.cache.exception import CacheError
from aiorequestful.cache.session import CachedSession
from aiorequestful.request import RequestHandler
from aiorequestful.types import JSON
from numpy.lib._datasource import Repository
from pydantic import Field, InstanceOf, AliasPath, PositiveInt, validate_call, TypeAdapter, \
    PrivateAttr, model_validator, ModelWrapValidatorHandler, AliasChoices
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import PydanticUndefined
from yarl import URL

from musify._types import get_base_types
from musify.models import ResourceModel
from musify.models._attribute import AttributeMetaclass
from musify.models._context import RemoteModelContext
from musify.models.api.types import ApiURL, _ApiURLSchema, _ApiURISchema, ApiURISequence
from musify.models.collection import RemoteCollection
from musify.models.cursors import PageCursor, HasPageCursor, IterablePageCursor, IndexCursor, InitialCursor
from musify.models.exception import APIModelError, RequestError, CursorResponseError, MusifyValidationError
from musify.models.properties.image import ImageSource, PILImageFileT, ImageURL
from musify.models.properties.logger import HasLogger
from musify.models.properties.uri import URI, HasURI
from musify.models.remote import RemoteModel, RemoteResource


class EndpointsMetaclass(AttributeMetaclass):
    # TODO: migrate this to aiorequestful v2?
    def create_model[T: RemoteResource](
            cls,
            value: Any,
            context: RemoteModelContext,
            kind: str | type[T] = None,
    ) -> T:
        """Create an instance of the resource type handled by this API model from the given value."""
        kls = cast('type[Endpoints]', cls)
        if not kls.__final__:
            raise APIModelError("Can only create resources from final API models.")

        if isinstance(kind, type) and issubclass(kind, RemoteResource) and kind.__final__:
            # just try to create the resource directly if a final resource type is given
            return kind.model_validate(value, context=context)

        if kind is None:
            kind = kls.type

        # noinspection PyTypeChecker
        source_classes = [klass for klass in RemoteResource.registered_submodels if klass.source == kls.source]
        if not source_classes:
            raise APIModelError(f"No registered resource models found for source {kls.source!r}.")

        if isinstance(kind, str):
            type_classes = [klass for klass in source_classes if klass.type == kind]
        else:
            type_classes = [klass for klass in source_classes if issubclass(klass, kind)]
            kind = kind.__name__
        if not type_classes:
            raise APIModelError(f"Could not find a registered {kls.source!r} model for type {kind!r}.")

        return TypeAdapter(Union[*type_classes]).validate_python(value, context=context)


class Endpoints[UT: URI, RT: RemoteResource](RemoteModel, HasLogger, metaclass=EndpointsMetaclass):
    type: ClassVar[str | Type[RemoteResource]] = Field(
        description="The type of resources the endpoints of this API model handle.",
    )
    _bar_threshold: ClassVar[int] = PrivateAttr(
        # description="The minimum number of pages required to show a progress bar when paginating through items.",
        default=5,
    )
    # TODO: drop this on aiorequestful v2
    _id_path: ClassVar[str | AliasPath | AliasChoices] = PrivateAttr(
        # description="The path to the ID of an item in the API response.",
    )
    _url_path: ClassVar[str | AliasPath | AliasChoices] = PrivateAttr(
        # description="The path to the href of an item in the API response.",
    )

    _handler: InstanceOf[RequestHandler[Authoriser, JSON]] = PrivateAttr(
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
        key = "handler"
        if isinstance(value, Mapping) and set(value.keys()) == {key}:
            value = value[key]
        if not isinstance(value, RequestHandler):
            return handler(value)

        # in case of nested endpoints
        data = {
            name: {key: value} for name, info in cls.model_fields.items()
            if any(issubclass(kls, Endpoints) for kls in get_base_types(info.annotation))
        }

        self = handler(data)
        self._handler = value
        return self

    @property
    def _nested_endpoints(self) -> list[Endpoints]:
        return [
            endpoints for name in self.__class__.model_fields.keys()
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
        kind = self._get_type_value(self.type)
        return RemoteModelContext(user=self.user, type=kind)

    async def __aenter__(self) -> Self:
        if self._handler.closed:
            await self._handler.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if not self._handler.closed:
            await self._handler.__aexit__(exc_type, exc_val, exc_tb)

    @staticmethod
    def _batch_values(values: Iterable, limit: int) -> batched:
        """Batch the given values into sublists of the given size."""
        return itertools.batched(map(str, values), limit)

    @classmethod
    def create_uri(cls, value: Any) -> URI:
        """Create a URI for the resource type handled by this API model from the given ID."""
        context = RemoteModelContext(type=cls.type)
        return URI.get_adapter_for_source(cls.source).validate_python(value, context=context)

    # TODO: migrate this to aiorequestful v2
    # noinspection PyArgumentList
    @validate_call
    async def _get_all_items(
            self,
            cursor: PageCursor,
            path: str | AliasPath | AliasChoices,
            kind: str | Type | None = None,
            show_bar: bool = True,
    ) -> tuple[tuple[RT, ...], PageCursor]:
        """Get all items from a request with paginated responses using the fastest available method."""
        if cursor.next is None:
            self._handler.log("SKIP", cursor.url, message="Cursor already fully extended")
            return (), cursor

        collection_type = self._get_type_value(self.type)
        item_type = self._get_type_value(kind)
        amount = cursor.total or "all"

        if item_type != collection_type:
            message = f"Extending {collection_type} with {amount} {item_type}s"
        else:
            message = f"Getting {amount} {item_type}s"
        self._handler.log("INFO", cursor.url, message=message)

        items, cursor = await self._get_all_items_from_cursor(cursor, path=path, kind=kind, show_bar=show_bar)

        message = f"Retrieved "
        if cursor.total:
            message += f"{len(items):>6}/{cursor.total:<6}"
        else:
            message += f"{len(items):>6}"

        message += f" {item_type}s"
        if item_type != collection_type:
            message += f" for {collection_type}"

        self._handler.log("DONE", cursor.url, message=message)

        return items, cursor

    # TODO: migrate this to aiorequestful v2
    # noinspection PyArgumentList
    async def _get_all_items_from_cursor(
            self,
            cursor: PageCursor,
            path: str | AliasPath | AliasChoices,
            kind: str | Type | None = None,
            show_bar: bool = True,
    ) -> tuple[tuple[RT, ...], PageCursor]:
        match cursor:
            case IterablePageCursor():
                return await self._get_all_items_by_generation(cursor, path=path, kind=kind, show_bar=show_bar)
            case _:
                return await self._get_all_items_by_pagination(cursor, path=path, kind=kind, show_bar=show_bar)

    # TODO: migrate this to aiorequestful v2
    @validate_call
    async def _get_all_items_by_pagination(
            self,
            cursor: PageCursor,
            path: str | AliasPath | AliasChoices,
            kind: str | Type | None = None,
            show_bar: bool = True,
    ) -> tuple[tuple[RT, ...], PageCursor]:
        """
        Get all items by paginating through the cursor, which must have a next URL for the first page of items.

        This is usually the slower approach, but is more widely supported as it does not require the API
        to provide the total number of items, offset and limit in the page cursor.
        """
        item_type = self._get_type_value(kind)
        items: list[RT] = []

        while cursor.next is not None:
            cursor: PageCursor = cursor.next
            response = await self._get_page(cursor, item_type=item_type, path=path)

            response_items = self._get_items_from_response(response=response, path=path)
            await self._cache_responses(response_items)

            items.extend(
                self.__class__.create_model(it, context=self._model_context, kind=kind) for it in response_items
            )

            cursor = cursor.get_cursor_from_response(response=response, path=path)
            print("IMTES", len(items))
            print("CURSOR", cursor)

            if cursor.next == cursor:
                raise CursorResponseError(
                    "The next cursor is the same as the current cursor, which may cause an infinite loop."
                )

            if isinstance(cursor, IterablePageCursor):
                # switch to faster generation mode for the remaining pages
                # noinspection PyArgumentList
                response_items, cursor = await self._get_all_items_by_generation(
                    cursor, path=path, kind=kind, show_bar=show_bar
                )
                print("GEN", len(response_items))
                items.extend(response_items)
                break

        print("FINL", len(items))
        return tuple(items), cursor

    # TODO: migrate this to aiorequestful v2
    @validate_call
    async def _get_all_items_by_generation[T: IterablePageCursor](
            self,
            cursor: T,
            path: str | AliasPath | AliasChoices,
            kind: str | Type[RT] | None = None,
            show_bar: bool = True,
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

        collection_type = self._get_type_value(self.type)
        item_type = self._get_type_value(kind)
        desc_type = f"{collection_type} {item_type}" if item_type != collection_type else collection_type

        responses: list[JSON] = await self.logger.get_asynchronous_iterator(
            map(functools.partial(self._get_page, item_type=item_type, path=path), cursors),
            desc=f"Getting {desc_type}s",
            unit="pages",
            initial=0,
            total=len(cursors),
            disable=not show_bar or len(cursors) < self._bar_threshold,
        )

        print("COUNTS", [len(self._get_items_from_response(response=res, path=path)) for res in responses])
        print("COUNTS", sum([len(self._get_items_from_response(response=res, path=path)) for res in responses]))

        cursors = cursor.sort_responses(responses, path=path)
        response_items = [
            item for response in responses
            for item in self._get_items_from_response(response=response, path=path)
        ]
        await self._cache_responses(response_items)
        items: list[RT] = [
            self.__class__.create_model(item, context=self._model_context, kind=kind)
            for item in response_items
        ]

        return tuple(items), cursors[-1]

    # TODO: migrate this to aiorequestful v2
    async def _get_page(self, page: PageCursor, item_type: str, path) -> JsonSchemaValue:
        """Thin wrapper for sending a get request from a page cursor while also formatting a log message"""
        log_message = None
        if isinstance(page, IndexCursor):
            log_message = f"{page.offset:>6}/{page.total:<6} {item_type}s"

        p = await self._handler.get(page.url, log_message=log_message)
        print("IMTES", len(self._get_items_from_response(response=p, path=path)))
        print("CURSOR", page.get_cursor_from_response(response=p, path=path))
        return p

    # TODO: migrate this to aiorequestful v2
    @classmethod
    def _get_items_from_response(cls, response: JSON, path: str | AliasPath | AliasChoices) -> list[JSON]:
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
    def _get_items_from_response_nested(cls, response: JSON, path: str | AliasPath) -> list[JSON] | None:
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

        bar = self.logger.get_asynchronous_iterator(map(_get_response, values), disable=True)
        results = dict(await bar)

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
    def _get_value_from_response(cls, response: JSON, path: str | AliasPath | AliasChoices) -> Any | None:
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


class ReadItemEndpoints[UT: URI, RT: RemoteResource](Endpoints[UT, RT]):
    @_ApiURLSchema.validate_call()  # WORKAROUND: replace with @validate_call when supported
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
        return self.__class__.create_model(response, context=self._model_context)


class ReadItemsEndpoints[UT: URI, RT: RemoteResource](Endpoints[UT, RT]):
    _many_url: ClassVar[URL] = PrivateAttr(
        # description="The API endpoint to get multiple resources of this type in one call.",
    )
    _many_limit: ClassVar[PositiveInt] = PrivateAttr(
        # description="The maximum number of items that can be sent in each request.",
    )
    _many_path: ClassVar[str | AliasPath | AliasChoices] = PrivateAttr(
        # description="The path to the list of items in the API response. Use '*' for wildcard matching.",
    )

    @_ApiURISchema.validate_call("uris", is_sequence=True)  # WORKAROUND: replace with @validate_call when supported
    async def get_many(
            self, uris: ApiURISequence[UT, RT], limit: PositiveInt = None, show_bar: bool = True
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
        :param show_bar: Show progress bar for each batch of URIs.
        """
        item_type = self._get_type_value(self.type)

        if not uris:
            self._handler.log("SKIP", self._many_url, message=f"No {item_type}s given to add")
            return []

        if limit is None:
            limit = self._many_limit

        # TODO: drop this on aiorequestful v2
        cache_responses = await self._get_responses_from_cache(self._many_url, uris)
        cache_items = [
            self.__class__.create_model(response, context=self._model_context)
            for response in cache_responses.values() if response is not None
        ]
        uncached_uris = [uri for uri, response in cache_responses.items() if response is None]

        async def _get_items(batch: Collection) -> Iterator[RT]:
            url = self._generate_batch_url(self._many_url, batch)
            message = f"Getting {len(batch):>6} {item_type}s"
            response = await self._handler.get(url, log_message=message)

            response_items = self._get_items_from_response(response=response, path=self._many_path)
            return (self.__class__.create_model(it, context=self._model_context) for it in response_items)

        batches = list(self._batch_values(uncached_uris, limit))
        bar = self.logger.get_asynchronous_iterator(
            map(_get_items, batches),
            desc=f"Getting {item_type}s",
            unit="batches",
            initial=0,
            total=len(batches),
            disable=not show_bar or len(batches) < self._bar_threshold,
        )

        # TODO: amend this on aiorequestful v2
        items = cache_items + [item for batch in await bar for item in batch]
        items.sort(key=lambda it: uris.index(it.uri.id))

        return items

    @classmethod
    def _generate_batch_url(cls, base_url: URL, values: Iterable) -> URL:
        """Generate a URL for the API endpoint for batched requests."""
        return base_url.update_query(ids=",".join(map(str, values)))


class ReadCollectionEndpoints[UT: URI, RT: RemoteCollection, IT: RemoteResource](Endpoints[UT, RT]):
    _extend_path: ClassVar[str | AliasPath | AliasChoices] = PrivateAttr(
        # description="The path to the list of items in the API response. Use '*' for wildcard matching.",
    )
    _extend_type: ClassVar[str | RemoteResource] = PrivateAttr(
        # description="The type of the items in the collection."
    )

    @validate_call
    async def get_all(self, collection: PageCursor | HasPageCursor | RT, show_bar: bool = True) -> list[IT]:
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
                raise RequestError("Expected a collection or page cursor.")

        # noinspection PyArgumentList
        items, cursor = await self._get_all_items(
            cursor, path=self._extend_path, kind=self._extend_type, show_bar=show_bar
        )
        if isinstance(collection, RemoteCollection):
            items = itertools.chain.from_iterable((collection.items, items))
            collection.cursor = cursor

        return list(items)


class WriteCollectionEndpoints[UT: URI, RT: RemoteResource, IT: HasURI](
    ReadItemEndpoints[UT, RT], ReadCollectionEndpoints[UT, RT, IT],
):
    _write_limit: ClassVar[PositiveInt] = PrivateAttr(
        # description="The maximum number of items that can be sent in each request for writing items.",
    )
    _extend_type: ClassVar[str | RemoteResource] = PrivateAttr(
        # description="The type of the items in the collection."
    )

    @_ApiURLSchema.validate_call()  # WORKAROUND: replace with @validate_call when supported
    @_ApiURISchema.validate_call("uris", is_sequence=True)
    async def add(
            self, url: ApiURL[UT, RT], uris: ApiURISequence[UT, IT], limit: PositiveInt = None, show_bar: bool = True
    ) -> int:
        """Add items to the current user's saved items for this endpoint resource type."""
        collection_type = self._get_type_value(self.type)
        item_type = self._get_type_value(self._extend_type)

        if not uris:
            self._handler.log("SKIP", url, message=f"No {item_type}s given to add")
            return 0

        if limit is None:
            limit = self._write_limit

        async def _post_items(batch: Collection) -> None:
            body = self._generate_append_batch_body(batch)
            message = f"Adding {len(batch):>6} {item_type}s to {collection_type}"
            await self._handler.post(url, json=body, log_message=message)

        batches = list(self._batch_values(uris, limit))
        await self.logger.get_asynchronous_iterator(
            map(_post_items, batches),
            desc=f"Adding {item_type}s to {collection_type}",
            unit="batches",
            initial=0,
            total=len(batches),
            disable=not show_bar or len(batches) < self._bar_threshold,
        )

        self._handler.log("DONE", url, message=f"Added {len(uris):>6} {item_type}s to {collection_type}")
        return len(uris)

    @staticmethod
    def _generate_append_batch_body(values: Iterable[str]) -> JsonSchemaValue:
        """Generate a request body for the API endpoint for append batched requests."""
        return {"uris": list(map(str, values))}

    @_ApiURLSchema.validate_call()  # WORKAROUND: replace with @validate_call when supported
    @_ApiURISchema.validate_call("uris", is_sequence=True)
    async def add_and_skip_duplicates(
            self, url: ApiURL[UT, RT], uris: ApiURISequence[UT, IT], limit: PositiveInt = None
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
        return await self.add(url, uris_unique, limit=limit)

    @_ApiURLSchema.validate_call()  # WORKAROUND: replace with @validate_call when supported
    @_ApiURISchema.validate_call("uris", is_sequence=True)
    async def remove(
            self, url: ApiURL[UT, RT], uris: ApiURISequence[UT, IT], limit: PositiveInt = None, show_bar: bool = True
    ) -> int:
        """Remove items from the current user's saved items for this endpoint resource type."""
        collection_type = self._get_type_value(self.type)
        item_type = self._get_type_value(self._extend_type)

        if not uris:
            self._handler.log("SKIP", url, message=f"No {item_type}s given to remove")
            return 0

        if limit is None:
            limit = self._write_limit

        async def _delete_items(batch: Collection) -> None:
            body = self._generate_remove_batch_body(batch)
            message = f"Removing {len(batch):>6} {item_type}s from {collection_type}"
            await self._handler.delete(url, json=body, log_message=message)

        batches = list(self._batch_values(uris, limit))
        await self.logger.get_asynchronous_iterator(
            map(_delete_items, batches),
            desc=f"Removing {item_type}s from {collection_type}",
            unit="batches",
            initial=0,
            total=len(batches),
            disable=not show_bar or len(batches) < self._bar_threshold,
        )

        self._handler.log("DONE", url, message=f"Removed {len(uris):>6} {item_type}s from {collection_type}")
        return len(uris)

    @staticmethod
    def _generate_remove_batch_body(values: Iterable[str]) -> JsonSchemaValue:
        """Generate a request body for the API endpoint for remove batched requests."""
        return {"uris": list(map(str, values))}


_INITIAL_CURSOR_ADAPTER = TypeAdapter[InitialCursor](InitialCursor.annotation)


class ReadSavedEndpoints[UT: URI, RT: RemoteResource](Endpoints[UT, RT]):
    _read_url: ClassVar[URL] = PrivateAttr(
        # description="The API endpoint to get the current user's saved items.",
    )
    _read_limit: ClassVar[PositiveInt] = PrivateAttr(
        # description="The maximum number of items that can be sent in each request for reading saved items.",
    )
    _read_path: ClassVar[str | AliasPath | AliasChoices] = PrivateAttr(
        # description="The path to the list of saved items in the API response. Use '*' for wildcard matching.",
    )

    @validate_call
    async def get_all(self, limit: PositiveInt | None = None, show_bar: bool = True) -> list[RT]:
        """Get the current user's saved items for this endpoint resource type."""
        if limit is None:
            limit = self._read_limit

        # we don't know what type of pagination will be used for saved items
        # just get a cursor which returns a url to begin pagination and figure it out later
        cursor = _INITIAL_CURSOR_ADAPTER.validate_python(dict(url=self._read_url, limit=limit))

        # noinspection PyArgumentList
        items, *_ = await self._get_all_items(cursor, path=self._read_path, kind=self.type, show_bar=show_bar)
        return list(items)


class WriteSavedEndpoints[UT: URI, RT: RemoteResource](Endpoints[UT, RT]):
    _write_url: ClassVar[URL] = PrivateAttr(
        # description="The API endpoint to modify the current user's saved items.",
    )
    _write_limit: ClassVar[PositiveInt] = PrivateAttr(
        # description="The maximum number of items that can be sent in each request for writing saved items.",
    )

    @_ApiURISchema.validate_call("uris", is_sequence=True)  # WORKAROUND: replace with @validate_call when supported
    async def add_many(self, uris: ApiURISequence[UT, RT], limit: PositiveInt = None, show_bar: bool = True) -> int:
        """Add items to the current user's saved items for this endpoint resource type."""
        item_type = self._get_type_value(self.type)

        if not uris:
            self._handler.log("SKIP", self._write_url, message=f"No {item_type}s given to add")
            return 0

        if limit is None:
            limit = self._write_limit

        async def _post_items(batch: Collection) -> None:
            kwargs = self._generate_add_batch_kwargs(batch)
            message = f"Adding {len(batch):>6} {item_type}s"
            await self._handler.put(self._write_url, log_message=message, **kwargs)

        batches = list(self._batch_values(uris, limit))
        await self.logger.get_asynchronous_iterator(
            map(_post_items, batches),
            desc=f"Adding {item_type}s",
            unit="batches",
            initial=0,
            total=len(batches),
            disable=not show_bar or len(batches) < self._bar_threshold,
        )

        self._handler.log("DONE", self._write_url, message=f"Added {len(uris):>6} {item_type}s")
        return len(uris)

    @staticmethod
    def _generate_add_batch_kwargs(values: Iterable[Any]) -> dict[str, JsonSchemaValue]:
        """Generate a request body for the API endpoint for batched requests."""
        return {"json": {"ids": list(map(str, values))}}

    @_ApiURISchema.validate_call("uris", is_sequence=True)  # WORKAROUND: replace with @validate_call when supported
    async def remove_many(self, uris: ApiURISequence[UT, RT], limit: PositiveInt = None, show_bar: bool = True) -> int:
        """Remote items from the current user's saved items for this endpoint resource type."""
        item_type = self._get_type_value(self.type)

        if not uris:
            self._handler.log("SKIP", self._write_url, message=f"No {item_type}s given to remove")
            return 0

        if limit is None:
            limit = self._write_limit

        async def _delete_items(batch: Collection) -> None:
            kwargs = self._generate_remove_batch_kwargs(batch)
            message = f"Removing {len(batch):>6} {item_type}s"
            await self._handler.delete(self._write_url, log_message=message, **kwargs)

        batches = list(self._batch_values(uris, limit))
        await self.logger.get_asynchronous_iterator(
            map(_delete_items, batches),
            desc=f"Removing {item_type}s",
            unit="batches",
            initial=0,
            total=len(batches),
            disable=not show_bar or len(batches) < self._bar_threshold,
        )

        self._handler.log("DONE", self._write_url, message=f"Removed {len(uris):>6} {item_type}s")
        return len(uris)

    @staticmethod
    def _generate_remove_batch_kwargs(values: Iterable[Any]) -> dict[str, JsonSchemaValue]:
        """Generate a request body for the API endpoint for batched requests."""
        return {"json": {"ids": list(map(str, values))}}


class HasEndpoints(RemoteModel):
    @property
    def _handler(self) -> RequestHandler:
        return next(getattr(self, field_name)._handler for field_name in self.__class__.model_fields.keys())

    @model_validator(mode="wrap")
    @classmethod
    def _from_handler[T](cls, value: T | RequestHandler, handler: ModelWrapValidatorHandler[Self]) -> Self:
        key = "handler"
        if isinstance(value, Mapping) and set(value.keys()) == {key}:
            value = value[key]
        if not isinstance(value, RequestHandler):
            return handler(value)

        data = {
            name: {key: value} for name, info in cls.model_fields.items()
            if issubclass(info.annotation, Endpoints)
        }

        self = handler(data)
        if isinstance(self, Endpoints):
            self._handler = value

        return self

    @model_validator(mode="after")
    def _all_handlers_are_the_same(self) -> Self:
        # noinspection PyProtectedMember
        handlers = {id(getattr(self, field_name)._handler) for field_name in self.__class__.model_fields.keys()}
        if len(handlers) != 1:
            raise MusifyValidationError(
                "All endpoint models must use the same request handler for API to function correctly."
            )

        return self

    @property
    def _nested_endpoints(self) -> list[Endpoints]:
        return [
            endpoints for name in self.__class__.model_fields.keys()
            if isinstance(endpoints := getattr(self, name), Endpoints)
        ]

    async def __aenter__(self) -> Self:
        for endpoints in self._nested_endpoints:
            await endpoints.__aenter__()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        for endpoints in self._nested_endpoints:
            await endpoints.__aexit__(exc_type, exc_val, exc_tb)


class HasSavedEndpoints[ET: ReadSavedEndpoints | WriteSavedEndpoints](HasEndpoints):
    saved: ET = Field(
        description="Access endpoints for the current user's saved items.",
    )
