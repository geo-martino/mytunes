from musify.models.collection.playlist import Playlist, MutablePlaylist
from musify.models.properties.uri import URI
from musify.remote._base import RemoteResource
from musify.remote.collection._base import RemoteCollection
from musify.remote.item.track import RemoteTrack


class RemotePlaylist[TK, TV: RemoteTrack, UT: URI](
    Playlist[TK, TV], RemoteResource[UT], RemoteCollection
):
    pass


class RemoteMutablePlaylist[TK, TV: RemoteTrack, UT: URI](
    MutablePlaylist[TK, TV], RemotePlaylist[TK, TV, UT]
):
    pass
