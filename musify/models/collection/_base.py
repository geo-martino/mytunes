from abc import abstractmethod
from typing import Collection, Iterable, TYPE_CHECKING

from pydantic import Field, NonNegativeInt

from musify.models import ResourceModel, BaseModel, abstract_property
from musify.models.cursors import PageCursor, HasPageCursor
from musify.models.properties.uri import URI
from musify.models.remote import RemoteResource
from musify.models.result import Result

if TYPE_CHECKING:
    from musify.models.api import HasEndpoints


# noinspection PyAbstractClass
class CollectionModel[IT: ResourceModel](BaseModel):
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


# noinspection PyAbstractClass
class RemoteCollection[UT: URI, IT: RemoteResource, CT: PageCursor](
    CollectionModel[IT], RemoteResource[UT], HasPageCursor[CT]
):
    @property
    def has_all_items(self) -> bool | None:
        """Whether this collection has all items loaded."""
        if self.cursor.total is None:
            return None
        return self.count == self.cursor.total

    @abstractmethod
    async def extend(self, api: HasEndpoints) -> None:
        """Extend this collection by loading all remaining pages of items using the provided API."""
        raise NotImplementedError


class SyncResult(Result):
    """Stores the results of a sync with a remote service."""
    start: NonNegativeInt = Field(
        description="The total number of items in the resource before the sync."
    )
    added: NonNegativeInt = Field(
        description="The number of items added to the resource."
    )
    removed: NonNegativeInt = Field(
        description="The number of items removed to the resource."
    )
    unchanged: NonNegativeInt = Field(
        description="The number of items that were in the remote resource both before and after the sync."
    )
    difference: int = Field(
        description="The difference between the total number items from before and after the sync."
    )
    final: NonNegativeInt = Field(
        description="The total number of items in the resource after the sync."
    )
