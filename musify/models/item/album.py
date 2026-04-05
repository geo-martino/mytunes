from typing import ClassVar, TYPE_CHECKING, Self, Annotated

from pydantic import Field, field_validator, computed_field, validate_call

from musify.models import ResourceModel
from musify.models._attribute import AttributeModel
from musify.models._metaclass import makecls
from musify.models.api import ItemReadEndpoints
from musify.models.api.items import HasAlbumEndpoints
from musify.models.item.artist import HasArtists, Artist, RemoteArtist
from musify.models.item.genre import HasGenres, Genre, RemoteGenre
from musify.models.metadata import TagAttribute, Attribute
from musify.models.properties.tag import HasSeparableTags
from musify.models.properties.date import HasReleaseDate
from musify.models.properties.image import HasImages
from musify.models.properties.length import HasLength
from musify.models.properties.name import HasName
from musify.models.properties.rating import HasRating
from musify.models.properties.uri import URI
from musify.models.remote import RemoteResource


class Album[RT: Artist, GT: Genre](
    HasArtists[RT],
    HasGenres[GT],
    HasName,
    HasLength,
    HasRating,
    HasReleaseDate,
    HasImages,
    ResourceModel,
    metaclass=makecls()
):
    type: ClassVar[str] = "album"

    compilation: Annotated[bool | None, Attribute()] = Field(
        description="Is this a compilation album",
        default=None,
    )

    @field_validator("artists", mode="before", check_fields=True)
    @classmethod
    def _validate_artists[T](cls, value: T) -> T | list:
        match value:
            case list() if all(isinstance(item, list) for item in value):
                value = [v for val in value for v in val]
        return value

    @field_validator("compilation", mode="before", check_fields=True)
    @classmethod
    def _validate_compilation[T](cls, value: T) -> T | bool | None:
        match value:
            case str():
                value = bool(value)
            case list():
                value = bool(next(iter(value), None))

        return value


class HasAlbum[AT: Album](AttributeModel):
    album: Annotated[AT | None, Attribute()] = Field(
        description="The album associated with this resource.",
        default=None,
    )

    @computed_field(
        description="The main artist on the album.",
    )
    @property
    def album_artist(self) -> Annotated[Artist | None, TagAttribute()]:
        """The main artist on the album."""
        if self.album is None or not self.album.artists:
            return None
        return self.album.artists[0]

    @album_artist.setter
    def album_artist(self, value: Artist) -> None:
        if self.album is None or value in self.album.artists:
            return
        if isinstance(value, str) and value in {artist.name for artist in self.album.artists}:
            return

        self.album.artists = [value, *(self.album.artists or ())]

    @computed_field(
        description="Whether the album is a compilation album.",
    )
    @property
    def compilation(self) -> Annotated[bool | None, TagAttribute()]:
        """Whether the album is a compilation album."""
        return self.album.compilation if self.album is not None else None

    @compilation.setter
    def compilation(self, value: bool | None) -> None:
        if self.album is None:
            return
        self.album.compilation = value


class HasAlbums[AT: Album](HasSeparableTags):
    albums: Annotated[list[AT], Attribute()] = Field(
        description="The albums associated with this resource.",
        default_factory=list,
        repr=False,
    )

    @field_validator("albums", mode="before", check_fields=True)
    @classmethod
    def _from_string[T: str](cls, value: T) -> T | list[str]:
        if not isinstance(value, str):
            return value
        return cls._separate_tags(value)


class RemoteAlbum[UT: URI, RT: RemoteArtist, GT: RemoteGenre](Album[RT, GT], RemoteResource[UT], metaclass=makecls()):
    @validate_call
    async def reload(self, api: HasAlbumEndpoints[ItemReadEndpoints]) -> None:
        model = await api.albums.get(self.uri)
        self.__dict__.update(model.__dict__)
