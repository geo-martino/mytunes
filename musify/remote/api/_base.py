import itertools
from collections.abc import MutableSequence, Collection, Iterable, Sequence
from itertools import batched
from typing import Any, ClassVar, Annotated

from aiorequestful.auth import Authoriser
from aiorequestful.request import RequestHandler
from aiorequestful.types import JSON
from pydantic import Field, InstanceOf, AliasPath, NonNegativeInt, PositiveInt, validate_call, TypeAdapter, PrivateAttr
from yarl import URL

from musify.exception import MusifyTypeError
from musify.models._base import AttributeModelMetaclass
from musify.models.properties.logger import HasLogger
from musify.models.properties.uri import URI
from musify.models.url import HttpURL
from musify.remote import RemoteResource, RemoteModel
from musify.remote.api._types import ApiURLSchema, ApiURISchema
from musify.remote.collection import ItemsCursor, RemoteCollection


class RemoteEndpointsMetaclass(AttributeModelMetaclass):
    def create[T: RemoteResource](cls: RemoteEndpoints[T], value: Any, kind: str = None) -> T:
        """Create an instance of the resource type handled by this API model from the given value."""
        if not cls.__final__:
            raise MusifyTypeError("Can only create resources from final API models.")

        if kind is None:
            kind = cls.type

        source_classes = [kls for kls in RemoteResource.registered_submodels if kls.source == cls.source]
        if not source_classes:
            raise MusifyTypeError(f"No registered resource models found for source {cls.source!r}.")

        for kls in source_classes:
            if kls.type == kind:
                return kls.model_validate(value)

        raise MusifyTypeError(f"Could not find a registered {cls.source!r} model for type {kind!r}.")


class RemoteEndpoints[AT: Authoriser, UT: URI, RT: RemoteResource](
    RemoteModel, HasLogger, metaclass=RemoteEndpointsMetaclass
):
    type: ClassVar[str] = Field(
        description="The type of resources the endpoints of this API model handle.",
    )

    handler: InstanceOf[RequestHandler[AT, JSON]] = Field(
        description="The handler for the API endpoint.",
    )

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
    async def _extend_items_from_cursor(
            self,
            items: MutableSequence[RT],
            cursor: ItemsCursor,
            path: str | AliasPath,
            kind: str = None,
    ) -> MutableSequence[RT]:
        while cursor.next is not None:
            response = await self.handler.get(cursor.next)
            self._extend_items_from_response(items=items, response=response, path=path, kind=kind)
            cursor = cursor.model_validate(response)

        return items

    @classmethod
    def _extend_items_from_response(
            cls,
            items: MutableSequence[RT],
            response: JSON,
            path: str | AliasPath,
            kind: str = None,
    ) -> None:
        match path:
            case str() as p:
                sub_items = response[p]
            case AliasPath() as p:
                sub_items = p.search_dict_for_path(response)

        items.extend((cls.create(it, kind=kind) for it in sub_items))


class RemoteGetSingleEndpoints[AT: Authoriser, UT: URI, RT: RemoteResource](RemoteEndpoints[AT, UT, RT]):
    # WORKAROUND: Replace decorator with validate_call when this issue is resolved:
    # https://github.com/pydantic/pydantic/issues/7796
    @ApiURLSchema.validate_call
    async def get(self, url: Annotated[URL, ApiURLSchema[UT, RT]], **kwargs) -> RT:
        """
        Get a resource from the API using the given ID, URL, URI, or resource.

        The URL given must relate to the resource type handled by this API model, and can be one of the following:
            * A URL (as a string or yarl.URL) pointing to the resource's API
            * A URI (as a string or URI object) for the resource
            * A resource object with a URI property for the resource
            * An ID (as a string) for the resource
        """
        response = await self.handler.get(url)
        return self.__class__.create(response)


class RemoteGetManyEndpoints[AT: Authoriser, UT: URI, RT: RemoteResource](RemoteEndpoints[AT, UT, RT]):
    _many_url: ClassVar[URL] = PrivateAttr(
        # description="The API endpoint to get multiple resources of this type in one call.",
    )
    _many_limit: ClassVar[str | AliasPath] = PrivateAttr(
        # description="The maximum number of items that can be sent in each request.",
    )
    _many_path: ClassVar[str | AliasPath] = PrivateAttr(
        # description="The path to the list of items in the API response.",
    )

    @ApiURISchema.validate_call
    async def get_many(self, uris: Sequence[Annotated[URI, ApiURISchema[UT, RT]]], limit: int = _many_limit) -> list[RT]:
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
        items = []
        for batch in self._batch_items(uris, limit):
            url = self._generate_many_url(batch)
            response = await self.handler.get(url)
            self._extend_items_from_response(items=items, response=response, path=self._many_path)

        return items

    @staticmethod
    def _batch_items(uris: Collection[URI], limit: int) -> batched[str]:
        """Batch the given URIs into sublists of the given size."""
        return itertools.batched(map(str, uris), limit)

    @classmethod
    def _generate_many_url(cls, values: Iterable[str]) -> URL:
        """Generate a URL for the API endpoint to get multiple resources."""
        return cls._many_url.update_query(ids=",".join(values))


class RemoteSavedEndpoints[AT: Authoriser, UT: URI, RT: RemoteResource](RemoteEndpoints[AT, UT, RT]):
    _saved_url: ClassVar[URL] = PrivateAttr(
        # description="The API endpoint to get the current user's saved items.",
    )
    _saved_path: ClassVar[str | AliasPath] = PrivateAttr(
        # description="The path to the list of saved items in the API response.",
    )

    @validate_call
    async def get_saved(self, limit: PositiveInt = None, offset: NonNegativeInt = None) -> list[RT]:
        """Get the current user's saved items for this endpoint resource type."""
        items: list[RT] = []
        cursor = self._create_saved_items_cursor(self._saved_url, limit=limit, offset=offset)
        await self._extend_items_from_cursor(items=items, cursor=cursor, path=self._saved_path, kind=self.type)
        return items


class RemoteCollectionEndpoints[AT: Authoriser, UT: URI, RT: RemoteCollection](RemoteEndpoints[AT, UT, RT]):
    _extend_path: ClassVar[str | AliasPath] = PrivateAttr(
        # description="The path to the list of items in the API response.",
    )
