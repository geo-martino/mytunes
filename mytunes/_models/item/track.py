from typing import ClassVar, Self, Annotated

from mytunes._models import ResourceModel
from mytunes._models._metaclass import makecls
from mytunes._models.api import ItemReadEndpoints
from mytunes._models.api.items import HasTrackEndpoints
from mytunes._models.item.album import HasAlbum, Album, RemoteAlbum
from mytunes._models.item.artist import HasArtists, Artist, RemoteArtist
from mytunes._models.item.genre import HasGenres, Genre, RemoteGenre
from mytunes._models.metadata import TagAttribute, Attribute
from mytunes._models.properties.date import HasReleaseDate
from mytunes._models.properties.image import HasImages
from mytunes._models.properties.length import HasLength
from mytunes._models.properties.music import HasKeySignature
from mytunes._models.properties.name import HasName
from mytunes._models.properties.order import Position, HasTrackPosition, HasDiscPosition
from mytunes._models.properties.rating import HasRating
from mytunes._models.properties.uri import URI
from mytunes._models.remote import RemoteResource
from mytunes._models.sequence import MutableUniqueSequence, UniqueSequence
from pydantic import Field, model_validator, PositiveInt, computed_field, PositiveFloat, validate_call

from .._base.attribute import AttributeModel


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
        from mytunes._models.collection.album import AlbumCollection

        if self.album is None:
            return self
        if not isinstance(self.album, AlbumCollection) or not (total := self.album.track_total):
            return self

        if self.track is not None:
            self.track.total = total
        elif self.track is None:
            self.__dict__["track"] = Position(total=total)

        return self

    @model_validator(mode="after")
    def _set_disc_total_from_album(self) -> Self:
        from mytunes._models.collection.album import AlbumCollection

        if self.album is None:
            return self
        if not isinstance(self.album, AlbumCollection) or not (total := self.album.disc_total):
            return self

        if self.disc is not None:
            self.disc.total = total
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


class HasTracks[TK, TV: Track](AttributeModel):
    """A mixin class to add a `tracks` field to a model."""
    tracks: Annotated[UniqueSequence[TK, TV], Attribute()] = Field(
        description="The tracks in this collection",
        default_factory=UniqueSequence[TK, TV],
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


class HasMutableTracks[TK, TV: Track](HasTracks[TK, TV]):
    """A mixin class to add a mutable `tracks` field to a model."""
    tracks: Annotated[MutableUniqueSequence[TK, TV], Attribute()] = Field(
        description="The tracks in this collection",
        default_factory=MutableUniqueSequence[TK, TV],
        frozen=True,
        repr=False,
    )


class RemoteTrack[UT: URI, RT: RemoteArtist, AT: RemoteAlbum, GT: RemoteGenre](
    Track[RT, AT, GT], RemoteResource[UT], metaclass=makecls()
):
    artists: Annotated[list[RT], Attribute()] = Field(
        description="The artists associated with this resource.",
        default_factory=list,
    )

    @validate_call
    async def reload(self, api: HasTrackEndpoints[ItemReadEndpoints]) -> None:
        model = await api.tracks.get(self.uri)
        self.__dict__.update(model.__dict__)
