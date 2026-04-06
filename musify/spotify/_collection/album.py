from typing import final, Self, Annotated

from pydantic import Field, AliasPath, PositiveInt, computed_field, model_validator

from musify.spotify.cursors import SpotifyIndexCursor
from .._item.album import SpotifyAlbum
from .._item.artist import SpotifyArtist
from .._item.genre import SpotifyGenre
from .._item.track import SpotifyTrack
from .._properties.uri import SpotifyResourceURI
from ..._models.collection.album import RemoteAlbumCollection
from ..._models.metadata import Attribute
from ..._models.sequence import UniqueSequence


# noinspection PyFinal
@final
class SpotifyAlbumCollection[RT: SpotifyArtist](
    SpotifyAlbum,
    RemoteAlbumCollection[SpotifyResourceURI, SpotifyTrack, RT, SpotifyGenre, SpotifyIndexCursor],
):
    __final__ = True

    tracks: Annotated[UniqueSequence[str, SpotifyTrack], Attribute()] = Field(
        description="The tracks on this album.",
        default_factory=UniqueSequence[str, SpotifyTrack],
        validation_alias=AliasPath("tracks", "items"),
        repr=False,
    )

    cursor: Annotated[SpotifyIndexCursor, Attribute()] = Field(
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
                track.__dict__["album"] = SpotifyAlbum(**self.model_dump())

            if track.released_at != self.released_at:
                track.__dict__["released_at"] = self.released_at
            if track.track is not None and track.track.total != self.track_total:
                track.track.__dict__["total"] = self.track_total
            if track.disc is not None and track.disc.total != self.disc_total:
                track.disc.__dict__["total"] = self.disc_total

        return self

    @computed_field(description="The total number of discs in this album")
    @property
    def disc_total(self) -> PositiveInt | None:
        if not self.tracks:
            return None

        return max(
            track.disc.number for track in self.tracks
            if track.disc is not None and track.disc.number is not None
        )
