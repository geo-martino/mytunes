from typing import Self

from pydantic import model_validator

from musify.models.properties.length import HasLength, Length
from musify.spotify.collection import SpotifyCollection


# noinspection PyAbstractClass
class HasSpotifyLength(HasLength):
    """A mixin for Spotify objects that have a length in milliseconds."""

    @model_validator(mode="after")
    def _set_length_from_items(self) -> Self:
        if not isinstance(self, SpotifyCollection) or not self.has_all_items:
            return self
        if not all(isinstance(item, HasLength) and item.length is not None for item in self._items):
            return self

        length = Length(sum(float(item.length) for item in self._items))
        if length != self.length:
            self.length = length
        return self
