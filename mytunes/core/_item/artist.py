from typing import ClassVar, Annotated, Self, Any

from pydantic import Field, field_validator, validate_call

from mytunes._types import to_list
from mytunes.core._item.genre import HasGenres, Genre, RemoteGenre
from mytunes.core.api import ItemReadEndpoints
from mytunes.core.api.items import HasArtistEndpoints
from mytunes.core.properties.name import HasName
from mytunes.core.properties.rating import HasRating
from mytunes.core.properties.tag import HasSeparableTags
from mytunes.core.properties.uri import URI
from mytunes.core.remote import RemoteResource
from mytunes.core.sequence import MutableUniqueSequence
from ..._base import makecls
from ..._base.attribute import Attribute
from ..._base.resource import ResourceModel


class Artist[GT: Genre](HasGenres[GT], HasName, HasRating, ResourceModel, metaclass=makecls()):
    """Represents an artist resource and its properties."""
    type: ClassVar[str] = "artist"


class HasArtists[RT: Artist](HasSeparableTags):
    artists: Annotated[MutableUniqueSequence[Any, RT], Attribute()] = Field(
        description="The artists associated with this resource.",
        default_factory=MutableUniqueSequence[Any, RT],
        validation_alias="artist",
    )

    @field_validator("artists", mode="before", check_fields=True)
    @classmethod
    def _from_string[T: str](cls, value: T) -> T | list[str]:
        if not isinstance(value, str):
            return value
        return cls._separate_tags(value)

    @property
    def artist(self) -> Annotated[str | None, Attribute()]:
        """A string representation of all artists featured on this resource"""
        return self._join_tags(artist.name for artist in self.artists)

    @artist.setter
    def artist(self, value: str | list[str]) -> None:
        if not value:
            self.artists = []
            return

        if isinstance(value, str):
            value = self._separate_tags(value)
        self.artists = to_list(value)


class RemoteArtist[UT: URI, GT: RemoteGenre](Artist[GT], RemoteResource[UT], metaclass=makecls()):
    @validate_call
    async def reload(self, api: HasArtistEndpoints[ItemReadEndpoints]) -> Self:
        model = await api.artists.get(self.uri)
        self.__dict__.update(model.__dict__)
        return model

