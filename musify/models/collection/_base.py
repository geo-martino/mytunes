import contextlib
from abc import abstractmethod
from collections.abc import Mapping
from copy import deepcopy
from typing import Collection, Iterable, Any, Self, TYPE_CHECKING, Generator, ClassVar

from pydantic import Field, NonNegativeInt, model_validator, ValidationError, TypeAdapter, PrivateAttr, AliasPath, \
    ModelWrapValidatorHandler
from pydantic_core import PydanticUndefined
from yarl import URL

from musify.exception import MusifyValueError
from musify.models import BaseResource, BaseModel, abstract_property
from musify.models.remote import RemoteModel, RemoteResource
from musify.models.url import HttpURL

if TYPE_CHECKING:
    from musify.models.api import HasEndpoints


# noinspection PyAbstractClass
class CollectionModel[IT: BaseResource](BaseModel):
    """Defines a common base models for attributes made of common collection properties."""
    @abstract_property
    def _items(self) -> Collection:
        """The items in this collection."""
        raise NotImplementedError

    @property
    def count(self) -> int:
        """The number of items currently stored in this collection."""
        return len(self._items)

    @property
    def iter_items(self) -> Iterable[IT]:
        """Iterator for the items currently stored in this collection."""
        return iter(self._items)


class PageCursor(RemoteModel):
    _limit_param_key: ClassVar[str] = "limit"
    _offset_param_key: ClassVar[str] = "offset"

    _next_path: ClassVar[str | AliasPath] = PrivateAttr(
        # description="The path to get the URL for the page of items"
        default="next"
    )
    _next_url_from_source: URL | None = PrivateAttr(
        # description="The path to get the URL for the page of items"
        default=None
    )

    url: HttpURL = Field(
        description="The URL to the current page of items",
        validation_alias="href",
    )
    limit: NonNegativeInt | None = Field(
        description="The maximum number of items returned per page.",
        default=None,
    )
    offset: NonNegativeInt | None = Field(
        description="The starting offset of the current page of items.",
        default=None,
    )
    total: NonNegativeInt | None = Field(
        description="The total number of items in the collection.",
        default=None,
    )

    @model_validator(mode="before")
    @classmethod
    def _from_url[T](cls, value: T) -> T | dict[str, Any]:
        with contextlib.suppress(ValidationError):
            url = TypeAdapter(HttpURL).validate_python(value)
            value = dict(url=url)

        return value

    @model_validator(mode="wrap")
    @classmethod
    def _get_next_url(cls, data: Any, handler: ModelWrapValidatorHandler[Self]) -> Self:
        if not isinstance(data, dict):
            return handler(data)

        match cls._next_path:
            case str() as path if path in data:
                url = data[path]
            case AliasPath() as path if (url := path.search_dict_for_path(data)) is not PydanticUndefined:
                pass
            case _:
                return handler(data)

        self = handler(data)
        with contextlib.suppress(ValidationError):
            self._next_url_from_source = TypeAdapter(HttpURL).validate_python(url)

        return self

    @model_validator(mode="after")
    def _get_limit_from_url(self) -> Self:
        if self.limit is not None:
            return self

        limit = self._get_param_value_from_url(self.url, param=self._limit_param_key)
        if limit is not None and (limit := int(limit)) != self.limit:
            self.limit = limit
        return self

    @model_validator(mode="after")
    def _set_limit_to_url(self) -> Self:
        match self.limit:
            case None:
                pass
            case 0 if self._limit_param_key in self.url.query:
                self.url = self.url.without_query_params(self._limit_param_key)
            case param if param > 0 and self.url.query.get(self._limit_param_key) != str(param):
                self.url = self.url.update_query({self._limit_param_key: param})

        return self

    @model_validator(mode="after")
    def _get_offset_from_url(self) -> Self:
        if self.offset is not None:
            return self

        offset = self._get_param_value_from_url(self.url, param=self._offset_param_key)
        if offset is not None and (offset := int(offset)) != self.offset:
            self.offset = offset
        return self

    @model_validator(mode="after")
    def _set_offset_to_url(self) -> Self:
        match self.offset:
            case None:
                pass
            case param if self.url.query.get(self._offset_param_key) != str(param):
                self.url = self.url.update_query({self._offset_param_key: param})

        return self

    @staticmethod
    def _get_param_value_from_url(url: URL, param: str) -> int | None:
        if param not in url.query:
            return

        value = url.query[param]
        if not value.isdigit():
            return
        return int(value)

    @property
    def _prev_url(self) -> URL | None:
        if self.offset is None or self.limit is None:
            raise MusifyValueError("Cannot generate previous URL without offset and limit.")
        if self.offset - self.limit < 0:
            return None
        return self.url.update_query(limit=self.limit, offset=self.offset - self.limit)

    @property
    def previous(self) -> Self | None:
        """The cursor for the previous page of items, if any."""
        if (url := self._prev_url) is None:
            return None
        return self.__class__(url=url, limit=self.limit, offset=self.offset - self.limit, total=self.total)

    @property
    def _next_url(self) -> URL | None:
        if self.total is None or self.offset is None or self.limit is None:
            if self._next_url_from_source is not None:
                return self._next_url_from_source
            raise MusifyValueError("Cannot generate next URL without offset, limit and total set.")
        if self.offset + self.limit > self.total:
            return None
        return self.url.update_query(limit=self.limit, offset=self.offset + self.limit)

    @property
    def next(self) -> Self | None:
        """The cursor for the next page of items, if any."""
        if (url := self._next_url) is None:
            return None
        return self.__class__(url=url, limit=self.limit, offset=self.offset + self.limit, total=self.total)

    @property
    def iter_next(self) -> Generator[Self, None, None]:
        """Iteratively generate the next cursors for the next pages of items, if any."""
        if not self.iterable:
            return

        cursor = self.next
        while cursor is not None:
            yield cursor
            cursor = cursor.next

    @property
    def iterable(self) -> bool:
        """Whether this cursor can be iterated to produce all next cursors."""
        return self.limit is not None and self.offset is not None and self.total is not None

    def reset(self) -> None:
        """Reset the current cursor to the first page of items."""
        self.offset = 0


# noinspection PyAbstractClass
class RemoteCollection[IT: RemoteResource, CT: PageCursor](RemoteModel, CollectionModel[IT]):
    total: NonNegativeInt | None = Field(
        description="The total number of items in this collection.",
        default=None,
    )
    cursor: CT = Field(
        description=(
            "The cursor for the current page of items. "
            "This is used for pagination and should be passed to the next page request to extend the collection."
        )
    )

    @property
    def has_all_items(self) -> bool | None:
        """Whether this collection has all items loaded."""
        if self.total is None:
            return None
        return self.count == self.total

    @abstractmethod
    def extend(self, api: HasEndpoints) -> None:
        """Extend this collection by loading all remaining pages of items using the provided API."""
        raise NotImplementedError
