from abc import abstractmethod
from typing import Collection, TYPE_CHECKING, Iterator

from musify.models import ResourceModel, BaseModel
from musify.models.cursors import PageCursor, HasPageCursor
from musify.models.properties.uri import URI
from musify.models.remote import RemoteResource

if TYPE_CHECKING:
    from musify.models.api import HasEndpoints


# noinspection PyAbstractClass
class CollectionModel[IT: ResourceModel](BaseModel):
    """Defines a common base models for attributes made of common collection properties."""
    @property
    @abstractmethod
    def _items(self) -> Collection:
        """The items in this collection."""
        raise NotImplementedError

    @property
    def items(self) -> Iterator[IT]:
        """Iterator for the items currently stored in this collection."""
        return iter(self._items)

    @property
    def count(self) -> int:
        """The number of items currently stored in this collection."""
        return len(self._items)


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
