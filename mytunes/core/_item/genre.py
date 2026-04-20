from typing import ClassVar, Annotated, Self, Any

from pydantic import Field, field_validator, validate_call

from mytunes._types import StrippedString
from mytunes.core.api import ItemReadEndpoints
from mytunes.core.api.items import HasGenreEndpoints
from mytunes.core.remote import RemoteResource
from mytunes.core.sequence import MutableUniqueSequence
from mytunes.properties.name import HasName
from mytunes.properties.tag import HasSeparableTags
from mytunes.properties.uri import URI
from ..._base import makecls
from ..._base.attribute import Attribute
from ..._base.resource import ResourceModel, UniqueAttribute


class Genre(HasName, ResourceModel, metaclass=makecls()):
    """Represents a genre resource and its properties."""
    type: ClassVar[str] = "genre"

    name: Annotated[StrippedString, UniqueAttribute()] = Field(
        description="The name of this genre.",
        alias="genre",
        frozen=True,
    )

    def __hash__(self) -> int:
        return hash(self.name)


class HasGenres[GT: Genre](HasSeparableTags):
    genres: Annotated[MutableUniqueSequence[Any, GT], Attribute()] = Field(
        description="The genres associated with this resource.",
        default_factory=MutableUniqueSequence[Any, GT],
        validation_alias="genre",
    )

    @field_validator("genres", mode="before", check_fields=True)
    @classmethod
    def _from_string[T: str](cls, value: T) -> T | list[str]:
        if not isinstance(value, str):
            return value
        return cls._separate_tags(value)

    @field_validator("genres", mode="before", check_fields=True)
    @classmethod
    def _from_model[T: Genre](cls, value: T) -> T | list[T]:
        if not isinstance(value, Genre):
            return value
        return [value]

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
    @validate_call
    async def reload(self, api: HasGenreEndpoints[ItemReadEndpoints]) -> Self:
        model = await api.genres.get(self.uri)
        self.__dict__.update(model.__dict__)
        return model
