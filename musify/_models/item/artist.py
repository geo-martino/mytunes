from typing import ClassVar, Annotated

from pydantic import Field, field_validator, validate_call

from musify._models import ResourceModel
from musify._models._metaclass import makecls
from musify._models.api import ItemReadEndpoints
from musify._models.api.items import HasArtistEndpoints
from musify._models.item.genre import HasGenres, Genre, RemoteGenre
from musify._models.metadata import Attribute
from musify._models.properties.name import HasName
from musify._models.properties.rating import HasRating
from musify._models.properties.tag import HasSeparableTags
from musify._models.properties.uri import URI
from musify._models.remote import RemoteResource
from musify._types import to_list


class Artist[GT: Genre](HasGenres[GT], HasName, HasRating, ResourceModel, metaclass=makecls()):
    """Represents an artist resource and its properties."""
    type: ClassVar[str] = "artist"


class HasArtists[RT: Artist](HasSeparableTags):
    artists: Annotated[list[RT], Attribute()] = Field(
        description="The artists associated with this resource.",
        default_factory=list,
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
    async def reload(self, api: HasArtistEndpoints[ItemReadEndpoints]) -> None:
        model = await api.artists.get(self.uri)
        self.__dict__.update(model.__dict__)

