from typing import ClassVar

from pydantic import Field, field_validator

from musify._types import StrippedString
from musify.models._base import CollectionResource
from musify.models.item.genre import HasGenres, Genre
from musify.models.properties import HasSeparableTags
from musify.models.properties.name import HasName
from musify.models.properties.rating import HasRating
from musify.models.properties.uri import URI, HasURI


class Artist[GT: Genre, UT: URI](HasGenres[GT], HasName, HasURI[UT], HasRating):
    """Represents an artist resource and its properties."""
    type: ClassVar[str] = "artist"

    name: StrippedString = Field(
        description="The name of this artist.",
        alias="artist",
    )


class HasArtists[RT: Artist](HasSeparableTags, CollectionResource[Artist]):
    artists: list[RT] = Field(
        description="The artists associated with this resource.",
        default_factory=list,
    )

    @property
    def _items(self) -> list[RT]:
        return self.artists

    # noinspection PyNestedDecorators
    @field_validator("artists", mode="before", check_fields=True)
    @classmethod
    def _from_string[T: str](cls, value: T) -> T | list[str]:
        if not isinstance(value, str):
            return value
        return cls._separate_tags(value)

    @property
    def artist(self) -> str | None:
        """A string representation of all artists featured on this resource"""
        return self._join_tags(artist.name for artist in self.artists)

    @artist.setter
    def artist(self, value: str | list[str]) -> None:
        if not value:
            self.artists = []
            return

        if isinstance(value, str):
            value = self._separate_tags(value)
        self.artists = value
