from datetime import datetime
from typing import Self

from pydantic import model_validator

from musify._models.collection import RemoteCollection
from musify._models.properties.date import HasAddedDate


class HasSpotifyAddedDate(HasAddedDate):
    @model_validator(mode="after")
    def _set_added_at_from_items(self) -> Self:
        if not isinstance(self, RemoteCollection) or self.count == 0 or not self.has_all_items:
            return self
        if not all(isinstance(item, HasAddedDate) and item.added_at is not None for item in self._items):
            return self

        # assume the first added item is the date this collection was added
        added_at: datetime = min(item.added_at for item in self._items)
        if added_at != self.added_at:
            self.__dict__["added_at"] = added_at
        return self
