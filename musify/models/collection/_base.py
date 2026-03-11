import contextlib
from abc import abstractmethod
from typing import Collection, Iterable, Any, Self

from pydantic import Field, NonNegativeInt, model_validator, ValidationError, TypeAdapter

from musify.models import BaseResource, BaseModel, abstract_property
from musify.models.remote import RemoteModel, RemoteResource
from musify.models.url import HttpURL


# noinspection PyAbstractClass
class CollectionModel[IT: BaseResource](BaseModel):
    """Defines a common base models for attributes made of common collection properties."""
    @abstract_property
    def _items(self) -> Collection:
        """The items in this collection."""
        raise NotImplementedError

    @property
    def items_count(self) -> int:
        """The number of items currently loaded in this collection."""
        return len(self._items)

    @property
    def items_iter(self) -> Iterable[IT]:
        """The number of items currently loaded in this collection."""
        return iter(self._items)


# noinspection PyAbstractClass
class CollectionResource[IT: BaseResource](CollectionModel[IT], BaseResource):
    """Defines a common base model for resources made of common collection properties."""


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
        if self.total is None:
            return None
        return self.items_count == self.total
