from musify.models.collection.playlist import Playlist, MutablePlaylist
from musify.models.properties.uri import URI
from musify.models.sequence import MusifySequence, MusifyMutableSequence
from musify.remote._base import RemoteResource
from musify.remote.collection._base import RemoteCollection
from musify.remote.item.track import RemoteTrack


class RemotePlaylist[TK, TV: RemoteTrack, UT: URI](
    Playlist[TK, TV, UT], RemoteResource[UT], RemoteCollection
):
    @property
    def _items(self) -> MusifySequence:
        return self.tracks


class RemoteMutablePlaylist[TK, TV: RemoteTrack, UT: URI](
    MutablePlaylist[TK, TV, UT], RemotePlaylist[TK, TV, UT]
):
    @property
    def _items(self) -> MusifyMutableSequence:
        return self.tracks
