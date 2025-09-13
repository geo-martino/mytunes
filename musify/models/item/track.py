from typing import ClassVar, Self

from pydantic import Field, model_validator, PositiveInt, computed_field

from musify._types import StrippedString
from musify.models._base import _CollectionModel
from musify.models.item.album import HasAlbum, Album
from musify.models.item.artist import HasArtists, Artist
from musify.models.item.genre import HasGenres, Genre
from musify.models.properties.date import HasReleaseDate
from musify.models.properties.image import HasImages
from musify.models.properties.length import HasLength
from musify.models.properties.music import KeySignature
from musify.models.properties.name import HasName
from musify.models.properties.order import Position
from musify.models.properties.rating import HasRating
from musify.models.properties.uri import HasURI
from musify.models.sequence import MusifyMutableSequence, MusifySequence


class TrackTagsMixin[RT: Artist, AT: Album, GT: Genre](
    HasArtists[RT], HasAlbum[AT], HasGenres[GT], HasName, HasRating, HasReleaseDate, HasImages
):
    """A mixin class to add common track tags which can be composed and written as metadata in a track file."""
    type: ClassVar[str] = "track"

    name: StrippedString = Field(
        description="The title of this track.",
        alias="title",
    )
    track: Position | None = Field(
        description="The position this track has on the album it is featured on.",
        default=None,
    )
    disc: Position | None = Field(
        description="The position of the disc in the album that this track is featured on.",
        default=None,
    )
    bpm: float | None = Field(
        description="The tempo of this track.",
        default=None,
    )
    key: KeySignature | None = Field(
        description="The key of this track.",
        default=None,
    )
    comments: list[str] = Field(
        description="Freeform comments that are associated with this track.",
        default_factory=list,
    )

    @model_validator(mode="after")
    def _set_track_total_from_album(self) -> Self:
        if self.album is None or (total := self.album.track_total) is None:
            return self

        if self.track is not None:
            self.track.total = total
        elif self.track is None:
            self.track = Position(total=total)

        return self

    @model_validator(mode="after")
    def _set_disc_total_from_album(self) -> Self:
        if self.album is None or (total := self.album.disc_total) is None:
            return self

        if self.disc is not None:
            self.disc.total = total
        elif self.disc is None:
            self.disc = Position(total=total)

        return self

    def __eq__(self, other: Self):
        if self is other:
            return True
        if not isinstance(other, Track):
            return False
        if super().__eq__(other):
            return True

        # match on track properties as last resort
        if not self.artists or not other.artists:
            return False
        if None in (self.album, other.album):
            return False

        self_artists = {artist.name for artist in self.artists}
        item_artists = {artist.name for artist in other.artists}

        return self.name == other.name and self_artists & item_artists and self.album.name == other.album.name


class Track[RT: Artist, AT: Album, GT: Genre](TrackTagsMixin[RT, AT, GT], HasURI, HasLength):
    """Represents a track resource and its properties."""
    pass


class HasTracks[TK, TV: Track](_CollectionModel):
    """A mixin class to add a `tracks` property to a MusifyCollection."""
    tracks: MusifySequence[TK, TV] = Field(
        description="The tracks in this collection",
        default_factory=MusifySequence[TK, TV],
        frozen=True,
    )

    @computed_field(description="The total number of tracks in this sequence")
    @property
    def track_total(self) -> PositiveInt:
        return len(self.tracks)

    @computed_field(description="The total number of discs in this sequence")
    @property
    def disc_total(self) -> PositiveInt | None:
        values = set(
            track.disc.total
            for track in self.tracks
            if track.disc is not None and track.disc.total is not None
        )
        return max(values) if values else None


class HasMutableTracks[TK, TV: Track](HasTracks[TK, TV]):
    """A mixin class to add a `tracks` property to a MusifyCollection."""
    tracks: MusifyMutableSequence[TK, TV] = Field(
        description="The tracks in this collection",
        default_factory=MusifyMutableSequence[TK, TV],
        frozen=True,
    )
