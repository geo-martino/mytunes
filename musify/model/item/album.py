from abc import ABC
from typing import ClassVar, Any

from pydantic import Field, field_validator, computed_field, PositiveInt

from musify._types import StrippedString
from musify.model._base import _AttributeModel, writeable_computed_field, abstract_property
from musify.model.item.artist import HasArtists, Artist
from musify.model.item.genre import HasGenres, Genre
from musify.model.properties import HasSeparableTags
from musify.model.properties.date import HasReleaseDate
from musify.model.properties.image import HasImages
from musify.model.properties.length import HasLength
from musify.model.properties.name import HasName
from musify.model.properties.rating import HasRating
from musify.model.properties.uri import HasURI


class _Album[RT: Artist, GT: Genre](
    ABC, HasArtists[RT], HasGenres[GT], HasName, HasURI, HasLength, HasRating, HasReleaseDate, HasImages
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
        abstract_property(),
        description="The total number of tracks on this album",
        return_type=PositiveInt | None,
    )
    # noinspection PyArgumentList
    disc_total = computed_field(
        abstract_property(),
        description="The total number of discs for this album",
        return_type=PositiveInt | None,
    )


class Album[RT: Artist, GT: Genre](_Album[RT, GT]):
    track_total = writeable_computed_field("track_total")
    disc_total = writeable_computed_field("disc_total")


class HasAlbum[T: Album](_AttributeModel):
    album: T | None = Field(
        description="The album associated with this resource.",
        default=None,
    )


class HasAlbums[T: Album](HasSeparableTags):
    albums: list[T] = Field(
        description="The albums associated with this resource.",
        default_factory=list,
    )

    # noinspection PyNestedDecorators
    @field_validator("albums", mode="before", check_fields=True)
    @classmethod
    def _from_string(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        return cls._separate_tags(value)
