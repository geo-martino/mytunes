from musify.models.collection.playlist import Playlist, MutablePlaylist
from musify.models.properties.uri import URI
from musify.models.sequence import MusifySequence, MusifyMutableSequence
from musify.remote._base import RemoteResource
from musify.remote.collection._base import RemoteCollection
from musify.remote.item.track import RemoteTrack


class RemotePlaylist[TT: RemoteTrack, UT: URI](
    Playlist[UT, TT, UT], RemoteResource[UT], RemoteCollection
):
    @property
    def _items(self) -> MusifySequence:
        return self.tracks


class RemoteMutablePlaylist[TT: RemoteTrack, UT: URI](
    MutablePlaylist[UT, TT, UT], RemotePlaylist[TT, UT]
):
    @property
    def _items(self) -> MusifyMutableSequence:
        return self.tracks
