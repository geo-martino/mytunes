from typing import ClassVar, TYPE_CHECKING, Self

from pydantic import Field, field_validator

from musify._types import StrippedString
from musify.models.collection import CollectionModel
from musify.models.properties import HasSeparableTags
from musify.models.properties.name import HasName
from musify.models.properties.uri import URI
from musify.models.remote import RemoteResource

if TYPE_CHECKING:
    from musify.models.api.genre import HasGenreEndpoints, GenreReadItemEndpoints


class Genre(HasName):
    """Represents a genre resource and its properties."""
    __unique_attributes__ = frozenset({"name"})

    type: ClassVar[str] = "genre"

    name: StrippedString = Field(
        description="The name of this genre.",
        alias="genre",
    )


class HasGenres[GT: Genre](HasSeparableTags, CollectionModel[GT]):
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


class RemoteGenre[UT: URI](Genre, RemoteResource[UT]):
    async def reload(self, api: HasGenreEndpoints[GenreReadItemEndpoints]) -> Self:
        return await api.genres.get(self.uri)
