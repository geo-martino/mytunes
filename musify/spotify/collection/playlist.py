from typing import final, Any

from pydantic import AliasPath, Field, model_validator, PositiveInt, NonNegativeInt

from musify.models.properties.date import HasAddedDate
from musify.models.sequence import MusifySequence, MusifyMutableSequence
from musify.remote.collection.playlist import RemotePlaylist, RemoteMutablePlaylist
from musify.spotify.collection._base import SpotifyCollection, SpotifyItemsCursor
from musify.spotify.item.track import SpotifyTrack
from musify.spotify.properties.followers import HasFollowers
from musify.spotify.properties.images import HasSpotifyImages
from musify.spotify.properties.uri import SpotifyResourceURI


@final
class SpotifyPlaylistTrack(SpotifyTrack, HasAddedDate):
    __final__ = True

    @model_validator(mode="before")
    def _extract_item_payload(cls, data: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(data, dict) or "item" not in data:
            return data

        data = {"added_at": data["added_at"]} | data["item"]
        return data


@final
class SpotifyPlaylist(
    RemotePlaylist[str, SpotifyPlaylistTrack, SpotifyResourceURI],
    SpotifyCollection,
    HasSpotifyImages,
    HasFollowers,
):
    __final__ = True

    tracks: MusifySequence[str, SpotifyPlaylistTrack] = Field(
        description="The tracks in this playlist.",
        default_factory=MusifySequence[str, SpotifyPlaylistTrack],
        validation_alias=AliasPath("items", "items")
    )

    total: NonNegativeInt = Field(
        description="The total number of tracks in this playlist.",
        validation_alias=AliasPath("items", "total")
    )
    cursor: SpotifyItemsCursor = Field(
        description=(
            "The cursor for the current page of tracks. "
            "This is used for pagination and should be passed to the next page request to extend the collection."
        ),
        validation_alias="items",
    )


@final
class SpotifyMutablePlaylist(
    RemoteMutablePlaylist[str, SpotifyPlaylistTrack, SpotifyResourceURI],
    SpotifyPlaylist,
):
    __final__ = True

    tracks: MusifyMutableSequence[str, SpotifyPlaylistTrack] = Field(
        description="The tracks in this playlist.",
        default_factory=MusifyMutableSequence[str, SpotifyPlaylistTrack],
        validation_alias=AliasPath("items", "items")
    )
