from collections.abc import MutableMapping
from typing import final, Any, ClassVar, Annotated

from pydantic import AliasPath, Field, model_validator, NonNegativeInt

from musify.exception import MusifyValueError
from musify.models.collection.playlist import RemotePlaylist, RemoteMutablePlaylist
from musify.models.exception import MusifyValidationError
from musify.models.metadata import Attribute
from musify.models.properties.date import HasAddedDate
from musify.models.sequence import UniqueSequence, MutableUniqueSequence
from musify.spotify import SpotifyResource
from musify.spotify.cursors import SpotifyIndexCursor, SpotifyInitialCursor
from musify.spotify.item.track import SpotifyTrack
from musify.spotify.properties.date import HasSpotifyAddedDate
from musify.spotify.properties.images import HasSpotifyImages
from musify.spotify.properties.length import HasSpotifyLength
from musify.spotify.properties.stats import HasFollowers
from musify.spotify.properties.uri import SpotifyResourceURI
from musify.spotify.user import SpotifyUser


# noinspection PyFinal
@final
class SpotifyPlaylistTrack(SpotifyTrack, HasAddedDate):
    __final__ = True

    @model_validator(mode="before")
    @classmethod
    def _extract_item_payload(cls, data: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(data, dict):
            return data

        if "item" not in data and "added_at" not in data:
            # need to ensure we don't accidentally validate playlist track for non-playlist track data
            raise MusifyValidationError("Expected 'item' key in playlist track data.")

        data = {"added_at": data["added_at"]} | data.get("item", data)
        return data


@final
class SpotifyPlaylist(
    SpotifyResource[SpotifyResourceURI],
    HasSpotifyLength,
    HasSpotifyImages,
    HasFollowers,
    HasSpotifyAddedDate,
    RemotePlaylist[SpotifyPlaylistTrack, SpotifyResourceURI, SpotifyUser, SpotifyIndexCursor],
):
    __final__ = True

    source: ClassVar[str] = "spotify"

    description: Annotated[str | None, Attribute()] = Field(
        description="The description of the playlist.",
        default=None,
    )
    collaborative: Annotated[bool, Attribute()] = Field(
        description="Whether the owner allows other users to modify the playlist.",
    )

    tracks: Annotated[UniqueSequence[str, SpotifyPlaylistTrack], Attribute()] = Field(
        description="The tracks in this playlist.",
        default_factory=UniqueSequence[str, SpotifyPlaylistTrack],
        validation_alias=AliasPath("items", "items"),
        frozen=True,
    )

    total: Annotated[NonNegativeInt, Attribute()] = Field(
        description="The total number of tracks in this playlist.",
        validation_alias=AliasPath("items", "total")
    )
    # getting current user's saved playlists return a 'starter' cursor of just the URL and total
    # we therefore need to support an InitialCursor here to support this
    cursor: Annotated[SpotifyIndexCursor | SpotifyInitialCursor, Attribute()] = Field(
        description=(
            "The cursor for the current page of tracks. "
            "This is used for pagination and should be passed to the next page request to extend the collection."
        ),
        validation_alias="items",
        union_mode="left_to_right",
    )

    @model_validator(mode="before")
    @classmethod
    def _drop_tracks[T](cls, data: T) -> T:
        if not isinstance(data, MutableMapping) or "items" not in data:
            return data

        data.pop("tracks", None)
        return data


# noinspection PyFinal
@final
class SpotifyMutablePlaylist(
    SpotifyPlaylist,
    RemoteMutablePlaylist[SpotifyPlaylistTrack, SpotifyResourceURI, SpotifyUser, SpotifyIndexCursor],
):
    __final__ = True

    tracks: Annotated[MutableUniqueSequence[str, SpotifyPlaylistTrack], Attribute()] = Field(
        description="The tracks in this playlist.",
        default_factory=MutableUniqueSequence[str, SpotifyPlaylistTrack],
        validation_alias=AliasPath("items", "items")
    )
