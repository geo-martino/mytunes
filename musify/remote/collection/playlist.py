from musify.models.collection.playlist import Playlist, MutablePlaylist
from musify.models.properties.uri import URI
from musify.remote.collection._base import RemoteCollection
from musify.remote.item.track import RemoteTrack


class RemotePlaylist[TK, TV: RemoteTrack, UT: URI](
    RemoteCollection[UT], Playlist[TK, TV]
):
    pass


class RemoteMutablePlaylist[TK, TV: RemoteTrack, UT: URI](
    RemotePlaylist[UT, TK, TV], MutablePlaylist[TK, TV]
):
    pass
