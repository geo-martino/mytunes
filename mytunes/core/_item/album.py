from typing import ClassVar, Annotated, Self

from pydantic import Field, field_validator, computed_field, validate_call

from mytunes.core._item.artist import HasArtists, Artist, RemoteArtist
from mytunes.core._item.genre import HasGenres, Genre, RemoteGenre
from mytunes.core.api import ItemReadEndpoints
from mytunes.core.api.items import HasAlbumEndpoints
from mytunes.core.properties.date import HasReleaseDate
from mytunes.core.properties.image import HasImages
from mytunes.core.properties.length import HasLength, HasTotal
from mytunes.core.properties.name import HasName
from mytunes.core.properties.rating import HasRating
from mytunes.core.properties.tag import HasSeparableTags
from mytunes.core.properties.uri import URI
from mytunes.core.remote import RemoteResource
from mytunes.core.sequence import UniqueSequence, MutableUniqueSequence
from ..._base import make_cls
from ..._base.attribute import AttributeModel, Attribute, TagAttribute
from ..._base.resource import ResourceModel


class Album[RT: Artist, GT: Genre](
    HasArtists[RT],
    HasGenres[GT],
    HasName,
    HasLength,
    HasRating,
    HasReleaseDate,
    HasImages,
    ResourceModel,
    metaclass=make_cls()
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
            case list() | UniqueSequence() if all(isinstance(item, list | UniqueSequence) for item in value):
                value = [v for val in value for v in val]
        return value

    @field_validator("compilation", mode="before", check_fields=True)
    @classmethod
    def _validate_compilation[T](cls, value: T) -> T | bool | None:
        match value:
            case str():
                value = bool(value)
            case list() | UniqueSequence():
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
    albums: Annotated[MutableUniqueSequence[AT], Attribute()] = Field(
        description="The albums associated with this resource.",
        default_factory=MutableUniqueSequence[AT],
        validation_alias="album",
        repr=False,
    )

    @field_validator("albums", mode="before", check_fields=True)
    @classmethod
    def _from_string[T: str](cls, value: T) -> T | list[str]:
        if not isinstance(value, str):
            return value
        return cls._separate_tags(value)


class RemoteAlbum[UT: URI, RT: RemoteArtist, GT: RemoteGenre](HasTotal, Album[RT, GT], RemoteResource[UT], metaclass=make_cls()):
    @validate_call
    async def reload(self, api: HasAlbumEndpoints[ItemReadEndpoints]) -> Self:
        model = await api.albums.get(self.uri)
        self.__dict__.update(model.__dict__)
        return model
