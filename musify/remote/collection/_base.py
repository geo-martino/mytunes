from abc import abstractmethod
from collections.abc import Collection

from pydantic import Field, InstanceOf, PositiveInt, NonNegativeInt
from yarl import URL

from musify.models import MusifyModel
from musify.remote._base import RemoteModel


class ItemsCursor(MusifyModel):
    current: InstanceOf[URL] = Field(
        description="The URL to the current page of items",
        validation_alias="href",
    )
    previous: InstanceOf[URL] | None = Field(
        description="The URL to the previous page of items, or null if there are no previous items.",
        default=None,
    )
    next: InstanceOf[URL] | None = Field(
        description="The URL to the next page of items, or null if there are no more items.",
        default=None,
    )
    limit: PositiveInt = Field(
        description="The maximum number of items returned per page.",
    )
    offset: NonNegativeInt = Field(
        description="The starting offset of the current page of items.",
    )


# noinspection PyAbstractClass
class RemoteCollection(RemoteModel):
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
    def _items(self) -> Collection:
        """The items in this collection."""
        raise NotImplementedError
