import sys
from collections.abc import MutableMapping
from typing import final, Annotated, Self, Literal, Any

from mytunes.spotify import SpotifyResource
from mytunes.spotify.cursors import SpotifyIndexCursor, SpotifyInitialCursor
from mytunes.spotify.user import SpotifyUser
from pydantic import AliasPath, Field, model_validator, NonNegativeInt
from pydantic.json_schema import JsonSchemaValue
from pydantic_core.core_schema import ValidationInfo

from .._item.track import SpotifyPlaylistTrack
from .._properties.date import HasSpotifyAddedDate
from .._properties.images import HasSpotifyImages
from .._properties.stats import HasFollowers
from .._properties.uri import SpotifyResourceURI
from ..._models.collection.playlist import RemotePlaylist, RemoteMutablePlaylist
from ..._models.exception import MyTunesValidationError
from ..._models.metadata import Attribute
from ..._models.sequence import UniqueSequence, MutableUniqueSequence


@final
class SpotifyPlaylist(
    SpotifyResource[SpotifyResourceURI],
    HasSpotifyImages,
    HasFollowers,
    HasSpotifyAddedDate,
    RemotePlaylist[SpotifyResourceURI, SpotifyPlaylistTrack, SpotifyUser, SpotifyIndexCursor],
):
    __final__ = True

    description: Annotated[str | None, Attribute()] = Field(
        description="The description of the playlist.",
        default=None,
    )
    collaborative: Annotated[Literal[False], Attribute()] = Field(
        description="Whether the owner allows other users to modify the playlist.",
        default=False,
    )

    tracks: Annotated[UniqueSequence[str, SpotifyPlaylistTrack], Attribute()] = Field(
        description="The tracks in this playlist.",
        default_factory=UniqueSequence[str, SpotifyPlaylistTrack],
        validation_alias=AliasPath("items", "items"),
        frozen=True,
        repr=False,
    )

    total: Annotated[NonNegativeInt, Attribute()] = Field(
        description="The total number of tracks in this playlist.",
        validation_alias=AliasPath("items", "total")
    )
    # getting current user's library playlists return a 'starter' cursor of just the URL and total
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

    @model_validator(mode="before")
    @classmethod
    def _add_items_if_missing[T](cls, data: T | MutableMapping[str, Any]) -> T | MutableMapping[str, Any]:
        if not isinstance(data, MutableMapping) or "items" in data or "cursor" in data:
            return data

        data["items"] = {"href": f"{data["href"]}/items", "total": sys.maxsize}
        return data


# noinspection PyFinal
@final
class SpotifyMutablePlaylist(
    SpotifyPlaylist,
    RemoteMutablePlaylist[SpotifyResourceURI, SpotifyPlaylistTrack, SpotifyUser, SpotifyIndexCursor],
):
    __final__ = True

    tracks: Annotated[MutableUniqueSequence[str, SpotifyPlaylistTrack], Attribute()] = Field(
        description="The tracks in this playlist.",
        default_factory=MutableUniqueSequence[str, SpotifyPlaylistTrack],
        validation_alias=AliasPath("items", "items"),
        repr=False,
    )
    collaborative: Annotated[bool, Attribute()] = Field(
        description="Whether the owner allows other users to modify the playlist.",
    )

    @model_validator(mode="after")
    def _validate_mutability(self, info: ValidationInfo) -> Self:
        if (user := self._get_context_user(info)) is None:
            return self

        if user != self.owner and not self.collaborative:
            raise MyTunesValidationError(
                "Currently authenticated user is not the owner of this playlist "
                f"({self.owner.name!r} != {user.name!r}) and playlist is not collaborative, "
                "which implies that this playlist is immutable. "
                "Use the appropriate immutable playlist type to validate this playlist instead."
            )

        return self

    def _get_properties_body(self) -> JsonSchemaValue:
        body = super()._get_properties_body()
        body["collaborative"] = self.collaborative
        body["image"] = next(iter(self.images.values()), None)
        return body
