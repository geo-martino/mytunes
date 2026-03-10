from typing import ClassVar

from pydantic import Field, field_validator

from musify._types import StrippedString
from musify.models._base import CollectionResource
from musify.models.properties import HasSeparableTags
from musify.models.properties.name import HasName


class Genre(HasName):
    """Represents a genre resource and its properties."""
    __unique_attributes__ = frozenset({"name"})

    type: ClassVar[str] = "genre"

    name: StrippedString = Field(
        description="The name of this genre.",
        alias="genre",
    )


class HasGenres[GT: Genre](HasSeparableTags, CollectionResource[GT]):
    genres: list[GT] = Field(
        description="The genres associated with this resource.",
        default_factory=list,
    )

    @property
    def _items(self) -> list[GT]:
        return self.genres

    # noinspection PyNestedDecorators
    @field_validator("genres", mode="before", check_fields=True)
    @classmethod
    def _from_string[T: str](cls, value: T) -> T | list[str]:
        if not isinstance(value, str):
            return value
        return cls._separate_tags(value)

    @property
    def genre(self) -> str | None:
        """A string representation of all genres associated with this resource"""
        return self._join_tags(genre.name for genre in self.genres)

    @genre.setter
    def genre(self, value: str | list[str]) -> None:
        if not value:
            self.genres = []
            return

        if isinstance(value, str):
            value = self._separate_tags(value)
        self.genres = value
