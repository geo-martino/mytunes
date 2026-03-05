from abc import ABCMeta, abstractmethod
from collections.abc import Collection

from pydantic import Field

from musify.remote._base import RemoteModel


class RemoteCollection(RemoteModel, metaclass=ABCMeta):
    total: int = Field(
        description="The total number of items in this collection."
    )

    @property
    def has_all_items(self) -> bool:
        """Whether this collection has all items loaded."""
        print(len(self._items), self.total)
        return len(self._items) == self.total

    @property
    @abstractmethod
    def _items(self) -> Collection:
        """The items in this collection."""
        raise NotImplementedError