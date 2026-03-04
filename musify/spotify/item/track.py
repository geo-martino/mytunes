from typing import final

from pydantic import Field, AliasChoices, AliasPath, field_validator

from musify.models.properties.length import Length
from musify.models.properties.order import Position
from musify.remote.item.track import RemoteTrack
from musify.spotify._base import SpotifyResource
from musify.spotify.item.album import SpotifyAlbum
from musify.spotify.item.artist import SpotifyArtist
from musify.spotify.properties.images import HasSpotifyImages
from musify.spotify.item.genre import SpotifyGenre
from musify.spotify.properties.popularity import HasPopularity
from musify.spotify.properties.uri import SpotifyResourceURI


@final
class SpotifyTrack(
    RemoteTrack[SpotifyResourceURI, SpotifyArtist, SpotifyAlbum, SpotifyGenre],
    SpotifyResource[SpotifyResourceURI],
    HasSpotifyImages,
    HasPopularity,
):
    __final__ = True

    disc: Position | None = Field(
        description="The position of the disc in the album that this track is featured on.",
        default=None,
        validation_alias="disc_number",
    )
    track: Position | None = Field(
        description="The position of the track on the album that this track is featured on.",
        default=None,
        validation_alias="track_number",
    )
    length: Length | None = Field(
        description="The length of this track in seconds.",
        default=None,
        validation_alias=AliasChoices(
            AliasPath("duration_ms", "totalMilliseconds"), "duration_ms"
        ),
    )
    uri: SpotifyResourceURI  # TODO: This shouldn't be needed...

    @field_validator("length", mode="before", check_fields=True)
    @classmethod
    def _convert_length_to_seconds[T](cls, duration_ms: T | int) -> T | float:
        if not isinstance(duration_ms, int | float):
            return duration_ms
        return int(duration_ms) / 1000
