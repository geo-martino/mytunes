import contextlib
from abc import abstractmethod
from copy import deepcopy
from typing import Collection, Iterable, Any, Self, TYPE_CHECKING, Generator

from pydantic import Field, NonNegativeInt, model_validator, ValidationError, TypeAdapter
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


class ItemsCursor(RemoteModel):
    current: HttpURL = Field(
        description="The URL to the current page of items",
        validation_alias="href",
    )
    previous: HttpURL | None = Field(
        description="The URL to the previous page of items, or null if there are no previous items.",
        default=None,
    )
    next: HttpURL | None = Field(
        description="The URL to the next page of items, or null if there are no more items.",
        default=None,
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
            value = dict(current=url)

        return value

    @model_validator(mode="after")
    def _set_limit_to_current_url(self) -> Self:
        param_key = "limit"

        match self.limit:
            case None:
                pass
            case 0 if param_key in self.current.query:
                self.current = self.current.without_query_params(param_key)
            case param if param > 0 and self.current.query.get(param_key) != str(param):
                self.current = self.current.update_query({param_key: param})

        return self

    @model_validator(mode="after")
    def _set_offset_to_current_url(self) -> Self:
        param_key = "offset"

        match self.offset:
            case None:
                pass
            case param if self.current.query.get(param_key) != str(param):
                self.current = self.current.update_query({param_key: param})

        return self

    @property
    def _current_from_next(self) -> URL:
        """Generate the next URL for the current page of items, using the current limit."""
        if self.offset is None or self.next is None:
            raise MusifyValueError("Cannot generate URL without offset and next URL.")
        return self.next.update_query(limit=self.limit, offset=self.offset)

    @property
    def _next_from_current(self) -> URL | None:
        """Generate the current URL for the next page of items, using the current limit."""
        if self.offset is None or self.limit is None:
            raise MusifyValueError("Cannot generate URL without offset and limit.")
        return self.current.update_query(limit=self.limit, offset=self.offset + self.limit)

    @property
    def iter_next(self) -> Generator[Self, None, None]:
        """Iteratively generate the next cursors for the next pages of items, if any."""
        if not self.iterable:
            yield from ()
            return

        if self.offset >= self.total:
            yield from ()
            return

        cursor = deepcopy(self)
        if cursor.next is None:
            cursor.next = cursor._next_from_current

        while cursor.offset + cursor.limit < self.total:
            cursor = deepcopy(cursor)
            cursor.offset += self.limit
            cursor.current = cursor.next
            cursor.next = cursor._next_from_current if cursor.offset + cursor.limit <= self.total else None

            yield cursor

    @property
    def iterable(self) -> bool:
        """Whether this cursor can be iterated to produce all next cursors."""
        return self.limit is not None and self.offset is not None and self.total is not None

    def reset(self) -> None:
        """Reset the current cursor to the first page of items."""
        self.previous = None
        self.next = None
        self.offset = 0


# noinspection PyAbstractClass
class RemoteCollection[IT: RemoteResource, CT: ItemsCursor](RemoteModel, CollectionModel[IT]):
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
        print(self.total, self.count)
        if self.total is None:
            return None
        return self.count == self.total

    @abstractmethod
    def extend(self, api: HasEndpoints) -> None:
        """Extend this collection by loading all remaining pages of items using the provided API."""
        raise NotImplementedError
