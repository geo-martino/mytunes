from pydantic import Field

from musify.models.collection.playlist import Playlist, MutablePlaylist
from musify.models.properties.uri import URI
from musify.remote._base import RemoteResource
from musify.remote.collection._base import RemoteCollection, ItemsCursor
from musify.remote.item.track import RemoteTrack
from musify.remote.user import RemoteUser


class RemotePlaylist[TT: RemoteTrack, UT: URI, OT: RemoteUser, CT: ItemsCursor](
    Playlist[UT, TT, UT], RemoteResource[UT], RemoteCollection[TT, CT]
):
    owner: OT = Field(
        description="The owner of this playlist.",
    )
    public: bool | None = Field(
        description="Whether this playlist is publicly available.",
        default=None,
    )


class RemoteMutablePlaylist[TT: RemoteTrack, UT: URI, OT: RemoteUser, CT: ItemsCursor](
    MutablePlaylist[UT, TT, UT], RemotePlaylist[TT, UT, OT, CT]
):
    pass
