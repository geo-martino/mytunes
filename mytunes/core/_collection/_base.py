from abc import abstractmethod
from collections.abc import Collection, Iterator
from typing import TYPE_CHECKING

from mytunes.core.cursors import PageCursor, HasPageCursor, InitialCursor
from mytunes.core.properties.uri import URI
from mytunes.core.remote import RemoteResource

from ..._base import BaseModel
from ..._base.resource import ResourceModel

if TYPE_CHECKING:
    from mytunes.core.api import HasEndpoints


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
    def _clear(self) -> None:
        """Clear the items in this collection."""
        raise NotImplementedError

    # @validate_call  # can't validate as can't import these types at runtime due to cyclical imports
    async def reload_items(self, api: HasEndpoints) -> None:
        """Replace all items in this collection by reloading all pages of items using the provided API."""
        self.cursor = InitialCursor.from_url(self.cursor.url, source=self.source)
        self._clear()
        await self.extend(api)

    @abstractmethod
    async def extend(self, api: HasEndpoints) -> None:
        """Extend this collection by loading all remaining pages of items using the provided API."""
        raise NotImplementedError
