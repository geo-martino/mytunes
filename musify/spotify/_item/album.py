from typing import final, Annotated

from pydantic import Field, field_validator

from musify._models.item.album import RemoteAlbum
from musify._models.metadata import Attribute
from musify._models.properties.date import SparseDate
from musify.spotify._base import SpotifyResource
from musify.spotify._item.artist import SpotifyArtist
from musify.spotify._item.genre import SpotifyGenre
from .._properties.images import HasSpotifyImages
from .._properties.rating import HasSpotifyRating
from .._properties.uri import SpotifyResourceURI


@final
class SpotifyAlbum(
    SpotifyResource[SpotifyResourceURI],
    HasSpotifyImages,
    HasSpotifyRating,
    RemoteAlbum[SpotifyResourceURI, SpotifyArtist, SpotifyGenre],
):
    __final__ = True

    released_at: Annotated[SparseDate, Attribute()] = Field(
        description="The date this album was released.",
        validation_alias="release_date",
    )
    compilation: Annotated[bool, Attribute()] = Field(
        description="Is this a compilation album",
        validation_alias="album_type",
    )

    @field_validator("compilation", mode="before")
    @classmethod
    def _is_compilation_album[T](cls, album_type: T | str) -> T | bool:
        if not isinstance(album_type, str):
            return album_type
        return album_type == "compilation"
