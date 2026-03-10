from typing import ClassVar

from pydantic import Field, field_validator, computed_field, PositiveInt

from musify._types import StrippedString
from musify.models._base import AttributeResource, CollectionResource
from musify.models.item.artist import HasArtists, Artist
from musify.models.item.genre import HasGenres, Genre
from musify.models.properties import HasSeparableTags
from musify.models.properties.date import HasReleaseDate
from musify.models.properties.image import HasImages
from musify.models.properties.length import HasLength
from musify.models.properties.name import HasName
from musify.models.properties.rating import HasRating
from musify.models.properties.uri import HasURI, URI


class Album[RT: Artist, GT: Genre, UT: URI](
    HasArtists[RT], HasGenres[GT], HasName, HasURI[UT], HasLength, HasRating, HasReleaseDate, HasImages
):
    type: ClassVar[str] = "album"

    name: StrippedString = Field(
        description="The name of this album.",
        alias="album",
    )
    compilation: bool | None = Field(
        description="Is this a compilation album",
        default=None,
    )
    # noinspection PyArgumentList
    track_total = computed_field(
        lambda x: None,
        description="The total number of tracks on this album",
        return_type=PositiveInt | None,
    )
    # noinspection PyArgumentList
    disc_total = computed_field(
        lambda x: None,
        description="The total number of discs for this album",
        return_type=PositiveInt | None,
    )


class HasAlbum[AT: Album](AttributeResource):
    album: AT | None = Field(
        description="The album associated with this resource.",
        default=None,
    )

    @property
    def compilation(self) -> bool | None:
        """Whether the album is a compilation album."""
        return self.album.compilation if self.album is not None else None


class HasAlbums[AT: Album](HasSeparableTags, CollectionResource[AT]):
    albums: list[AT] = Field(
        description="The albums associated with this resource.",
        default_factory=list,
    )

    @property
    def _items(self) -> list[AT]:
        return self.albums

    # noinspection PyNestedDecorators
    @field_validator("albums", mode="before", check_fields=True)
    @classmethod
    def _from_string[T: str](cls, value: T) -> T | list[str]:
        if not isinstance(value, str):
            return value
        return cls._separate_tags(value)
