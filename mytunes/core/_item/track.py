from typing import ClassVar, Self, Annotated, Any

from pydantic import Field, model_validator, PositiveInt, computed_field, PositiveFloat, validate_call

from mytunes.core._item.album import HasAlbum, Album, RemoteAlbum
from mytunes.core._item.artist import HasArtists, Artist, RemoteArtist
from mytunes.core._item.genre import HasGenres, Genre, RemoteGenre
from mytunes.core.api import ItemReadEndpoints
from mytunes.core.api.items import HasTrackEndpoints
from mytunes.core.remote import RemoteResource
from mytunes.core.sequence import MutableUniqueSequence, UniqueSequence
from mytunes.core.properties.date import HasReleaseDate
from mytunes.core.properties.image import HasImages
from mytunes.core.properties.length import HasLength
from mytunes.core.properties.music import HasKeySignature
from mytunes.core.properties.name import HasName
from mytunes.core.properties.order import Position, HasTrackPosition, HasDiscPosition
from mytunes.core.properties.rating import HasRating
from mytunes.core.properties.uri import URI
from ..._base import makecls
from ..._base.attribute import AttributeModel, Attribute, TagAttribute
from ..._base.resource import ResourceModel


class Track[RT: Artist, AT: Album, GT: Genre](
    HasArtists[RT],
    HasAlbum[AT],
    HasGenres[GT],
    HasName,
    HasTrackPosition,
    HasDiscPosition,
    HasRating,
    HasReleaseDate,
    HasImages,
    HasLength,
    HasKeySignature,
    ResourceModel,
    metaclass=makecls()
):
    """Represents a track resource and its properties."""
    type: ClassVar[str] = "track"

    bpm: Annotated[PositiveFloat | None, TagAttribute()] = Field(
        description="The tempo of this track.",
        default=None,
    )
    comments: Annotated[list[str], TagAttribute()] = Field(
        description="Freeform comments that are associated with this track.",
        default_factory=list,
    )

    @model_validator(mode="after")
    def _set_track_total_from_album(self) -> Self:
        from mytunes.core._collection.album import AlbumCollection

        if self.album is None:
            return self
        if not isinstance(self.album, AlbumCollection) or not (total := self.album.track_total):
            return self

        if self.track is not None:
            self.track.__dict__["total"] = total
        elif self.track is None:
            self.__dict__["track"] = Position(total=total)

        return self

    @model_validator(mode="after")
    def _set_disc_total_from_album(self) -> Self:
        from mytunes.core._collection.album import AlbumCollection

        if self.album is None:
            return self
        if not isinstance(self.album, AlbumCollection) or not (total := self.album.disc_total):
            return self

        if self.disc is not None:
            self.disc.__dict__["total"] = total
        elif self.disc is None:
            self.__dict__["disc"] = Position(total=total)

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


class HasTracks[TT: Track](AttributeModel):
    """A mixin class to add a `tracks` field to a model."""
    tracks: Annotated[UniqueSequence[Any, TT], Attribute()] = Field(
        description="The tracks in this collection",
        default_factory=UniqueSequence[Any, TT],
        frozen=True,
        repr=False,
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


class HasMutableTracks[TT: Track](HasTracks[TT]):
    """A mixin class to add a mutable `tracks` field to a model."""
    tracks: Annotated[MutableUniqueSequence[Any, TT], Attribute()] = Field(
        description="The tracks in this collection",
        default_factory=MutableUniqueSequence[Any, TT],
        frozen=True,
        repr=False,
    )


class RemoteTrack[UT: URI, RT: RemoteArtist, AT: RemoteAlbum, GT: RemoteGenre](
    Track[RT, AT, GT], RemoteResource[UT], metaclass=makecls()
):
    @validate_call
    async def reload(self, api: HasTrackEndpoints[ItemReadEndpoints]) -> Self:
        model = await api.tracks.get(self.uri)
        self.__dict__.update(model.__dict__)
        return model
