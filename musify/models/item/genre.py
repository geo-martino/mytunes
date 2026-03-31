from typing import ClassVar, TYPE_CHECKING, Self, Annotated

from pydantic import Field, field_validator

from musify._types import StrippedString
from musify.models import ResourceModel
from musify.models._metaclass import makecls
from musify.models.metadata import UniqueAttribute, Attribute
from musify.models.properties import HasSeparableTags
from musify.models.properties.name import HasName
from musify.models.properties.uri import URI
from musify.models.remote import RemoteResource

if TYPE_CHECKING:
    from musify.models.api.genre import HasGenreEndpoints, GenreReadItemEndpoints


class Genre(HasName, ResourceModel, metaclass=makecls()):
    """Represents a genre resource and its properties."""
    type: ClassVar[str] = "genre"

    name: Annotated[StrippedString, UniqueAttribute()] = Field(
        description="The name of this genre.",
        alias="genre",
    )


class HasGenres[GT: Genre](HasSeparableTags):
    genres: Annotated[list[GT], Attribute()] = Field(
        description="The genres associated with this resource.",
        default_factory=list,
    )

    # noinspection PyNestedDecorators
    @field_validator("genres", mode="before", check_fields=True)
    @classmethod
    def _from_string[T: str](cls, value: T) -> T | list[str]:
        if not isinstance(value, str):
            return value
        return cls._separate_tags(value)

    @property
    def genre(self) -> Annotated[str | None, Attribute()]:
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


class RemoteGenre[UT: URI](RemoteResource[UT], Genre, metaclass=makecls()):
    # @validate_call  # can't validate as can't import these types at runtime due to cyclical imports
    async def reload(self, api: HasGenreEndpoints[GenreReadItemEndpoints]) -> Self:
        return await api.genres.get(self.uri)
