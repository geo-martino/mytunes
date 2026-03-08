import contextlib
from abc import abstractmethod
from collections.abc import Collection, MutableSequence, Iterable
from typing import Any, Self

from pydantic import Field, PositiveInt, NonNegativeInt, model_validator, TypeAdapter, ModelWrapValidatorHandler, \
    ValidationError

from musify.models.sequence import MusifySequence
from musify.models.url import HttpURL
from musify.remote._base import RemoteModel, RemoteResource


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
    limit: PositiveInt | None = Field(
        description="The maximum number of items returned per page.",
        default=None,
    )
    offset: NonNegativeInt | None = Field(
        description="The starting offset of the current page of items.",
        default=None,
    )

    @model_validator(mode="wrap")
    @classmethod
    def _from_url(cls, value: Any, handler: ModelWrapValidatorHandler[Self]) -> Self:
        with contextlib.suppress(ValidationError):
            url = TypeAdapter(HttpURL).validate_python(value)
            return handler(dict(current=url))

        return handler(value)

    @model_validator(mode="after")
    def _set_limit_to_current_url(self) -> Self:
        if self.limit is not None and self.current.query.get("limit") != str(self.limit):
            self.current = self.current.update_query(limit=self.limit)
        return self

    @model_validator(mode="after")
    def _set_offset_to_current_url(self) -> Self:
        if self.offset is not None and self.current.query.get("offset") != str(self.offset):
            self.current = self.current.update_query(offset=self.offset)
        return self

    def reset(self) -> None:
        """Reset the current cursor to the first page of items."""
        self.previous = None
        self.next = None
        self.offset = 0


# noinspection PyAbstractClass
class RemoteCollection[IT: RemoteResource](RemoteModel):
    total: NonNegativeInt = Field(
        description="The total number of items in this collection."
    )
    cursor: ItemsCursor = Field(
        description=(
            "The cursor for the current page of items. "
            "This is used for pagination and should be passed to the next page request to extend the collection."
        )
    )

    @property
    def has_all_items(self) -> bool:
        """Whether this collection has all items loaded."""
        return len(self._items) == self.total

    @property
    @abstractmethod
    def _items(self) -> Collection[IT]:
        """The items in this collection."""
        raise NotImplementedError

    def _extend_items(self, other: Iterable[IT]) -> None:
        """Extend the items in this collection with the given items."""
        match self._items:
            case MutableSequence() as items:
                items.extend(other)
            case MusifySequence() as items:
                other = list(other)
                # noinspection PyProtectedMember
                items._items.extend(other)
                # noinspection PyProtectedMember
                items._items_mapped.update(other)
            case items:
                raise TypeError(f"Cannot extend items of type {type(items).__name__!r}.")
