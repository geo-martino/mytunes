from typing import final, Annotated

from pydantic import Field, field_validator, PositiveInt, computed_field, PrivateAttr

from mytunes.core.album import RemoteAlbum
from mytunes.core.properties.date import SparseDate
from mytunes.spotify._base import SpotifyResource
from mytunes.spotify._item.artist import SpotifyArtist
from mytunes.spotify._item.genre import SpotifyGenre
from .._properties.images import HasSpotifyImages
from .._properties.rating import HasSpotifyRating
from .._properties.uri import SpotifyResourceURI
from ..._base.attribute import Attribute


@final
class SpotifyAlbum(
    SpotifyResource[SpotifyResourceURI],
    HasSpotifyImages,
    HasSpotifyRating,
    RemoteAlbum[SpotifyResourceURI, SpotifyArtist, SpotifyGenre],
):
    __final__ = True
    __total: PositiveInt = PrivateAttr(
        default=0,
    )

    released_at: Annotated[SparseDate, Attribute()] = Field(
        description="The date this album was released.",
        validation_alias="release_date",
    )
    compilation: Annotated[bool, Attribute()] = Field(
        description="Is this a compilation album",
        validation_alias="album_type",
    )

    @computed_field(
        alias="total_tracks",
    )
    @property
    def total(self) -> Annotated[PositiveInt, Attribute()]:
        return self.__total

    @total.setter
    def total(self, total: PositiveInt):
        self.__total = total

    @field_validator("compilation", mode="before")
    @classmethod
    def _is_compilation_album[T](cls, album_type: T | str) -> T | bool:
        if not isinstance(album_type, str):
            return album_type
        return album_type == "compilation"
