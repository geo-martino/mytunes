from abc import abstractmethod
from typing import Collection, Iterable, TYPE_CHECKING

from pydantic import Field, NonNegativeInt

from musify.models import BaseResource, BaseModel, abstract_property
from musify.models.cursors import PageCursor, HasPageCursor
from musify.models.remote import RemoteResource

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


# noinspection PyAbstractClass
class RemoteCollection[IT: RemoteResource, CT: PageCursor](HasPageCursor[CT], CollectionModel[IT]):
    total: NonNegativeInt | None = Field(
        description="The total number of items in this collection.",
        default=None,
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
