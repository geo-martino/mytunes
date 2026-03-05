from abc import ABCMeta

from musify.models.collection.library import Library, MutableLibrary
from musify.remote.collection.playlist import RemotePlaylist
from musify.remote.item.track import RemoteTrack


class RemoteLibrary[TK, TV: RemoteTrack, KP, VP: RemotePlaylist](
    Library[TK, TV, KP, VP], metaclass=ABCMeta
):
    pass


class RemoteMutableLibrary[TK, TV: RemoteTrack, KP, VP: RemotePlaylist](
    MutableLibrary[TK, TV, KP, VP], RemoteLibrary[TK, TV, KP, VP], metaclass=ABCMeta
):
    pass
