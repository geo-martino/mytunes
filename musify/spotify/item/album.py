from typing import final

from pydantic import Field, field_validator

from musify.remote.item.album import RemoteAlbum
from musify.spotify._base import SpotifyResource
from musify.spotify.item.artist import SpotifyArtist
from musify.spotify.item.genre import SpotifyGenre
from musify.spotify.properties.images import HasSpotifyImages
from musify.spotify.properties.popularity import HasPopularity
from musify.spotify.properties.uri import SpotifyResourceURI


@final
class SpotifyAlbum(
    RemoteAlbum[SpotifyArtist, SpotifyGenre, SpotifyResourceURI],
    SpotifyResource[SpotifyResourceURI],
    HasSpotifyImages,
    HasPopularity,
):
    __final__ = True

    compilation: bool | None = Field(
        description="Is this a compilation album",
        default=None,
        validation_alias="album_type",
    )

    @field_validator("compilation", mode="before")
    @classmethod
    def _is_compilation_album[T](cls, album_type: T | str) -> T | bool:
        if not isinstance(album_type, str):
            return album_type
        return album_type == "compilation"
