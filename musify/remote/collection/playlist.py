from musify.models.collection.playlist import Playlist, MutablePlaylist
from musify.models.properties.uri import URI
from musify.remote._base import RemoteResource
from musify.remote.collection._base import RemoteCollection
from musify.remote.item.track import RemoteTrack


class RemotePlaylist[TK, TV: RemoteTrack, UT: URI](
    RemoteResource[UT], RemoteCollection, Playlist[TK, TV]
):
    pass


class RemoteMutablePlaylist[TK, TV: RemoteTrack, UT: URI](
    RemotePlaylist[TK, TV, UT], MutablePlaylist[TK, TV]
):
    pass
