from typing import ClassVar, Any

from pydantic import Field, field_validator

from musify._types import StrippedString
from musify.model.item.genre import HasGenres, Genre
from musify.model.properties import HasSeparableTags
from musify.model.properties.name import HasName
from musify.model.properties.rating import HasRating
from musify.model.properties.uri import HasURI


class _Artist[GT: Genre](HasGenres[GT], HasName, HasURI, HasRating):
    """Represents an artist resource and its properties."""
    type: ClassVar[str] = "artist"

    name: StrippedString = Field(
        description="The name of this artist.",
        alias="artist",
    )


class Artist[GT: Genre](_Artist[GT]):
    pass


class HasArtists[T: Artist](HasSeparableTags):
    artists: list[T] | None = Field(
        description="The artists associated with this resource.",
        default_factory=list[T],
    )

    # noinspection PyNestedDecorators
    @field_validator("artists", mode="before", check_fields=True)
    @classmethod
    def _from_string(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        return cls._separate_tags(value)

    @property
    def artist(self) -> str | None:
        """A string representation of all artists featured on this resource"""
        return self._join_tags(artist.name for artist in self.artists)
