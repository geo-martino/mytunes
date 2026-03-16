from typing import final, Self

from pydantic import Field, AliasPath, PositiveInt, computed_field, model_validator

from musify.models.collection.album import RemoteAlbumCollection
from musify.models.sequence import UniqueSequence
from musify.spotify.collection._base import SpotifyCollection
from musify.spotify.cursors import SpotifyIndexCursor
from musify.spotify.item.album import SpotifyAlbum
from musify.spotify.item.artist import SpotifyArtist
from musify.spotify.item.genre import SpotifyGenre
from musify.spotify.item.track import SpotifyTrack
from musify.spotify.properties.length import HasSpotifyLength
from musify.spotify.properties.uri import SpotifyResourceURI


# noinspection PyFinal
@final
class SpotifyAlbumCollection[RT: SpotifyArtist](
    SpotifyAlbum,
    SpotifyCollection[SpotifyTrack],
    HasSpotifyLength,
    RemoteAlbumCollection[SpotifyTrack, RT, SpotifyGenre, SpotifyResourceURI, SpotifyIndexCursor],
):
    __final__ = True

    tracks: UniqueSequence[str, SpotifyTrack] = Field(
        description="The tracks on this album.",
        default_factory=list,
        validation_alias=AliasPath("tracks", "items")
    )

    cursor: SpotifyIndexCursor = Field(
        description=(
            "The cursor for the current page of tracks. "
            "This is used for pagination and should be passed to the next page request to extend the collection."
        ),
        validation_alias="tracks",
    )

    @model_validator(mode="after")
    def _set_album_data_to_tracks(self) -> Self:
        for track in self.tracks:
            if track.album is None:
                track.album = SpotifyAlbum(**self.model_dump())

            if track.released_at != self.released_at:
                track.released_at = self.released_at
            if track.track is not None and track.track.total != self.track_total:
                track.track.total = self.track_total
            if track.disc is not None and track.disc.total != self.disc_total:
                track.disc.total = self.disc_total

        return self

    @computed_field(description="The total number of tracks in this album")
    @property
    def track_total(self) -> PositiveInt:
        return self.cursor.total

    @computed_field(description="The total number of discs in this album")
    @property
    def disc_total(self) -> PositiveInt | None:
        if not self.tracks:
            return None

        return max(
            track.disc.number for track in self.tracks
            if track.disc is not None and track.disc.number is not None
        )
