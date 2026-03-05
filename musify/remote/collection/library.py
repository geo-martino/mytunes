from abc import ABCMeta

from musify.models.collection.library import Library
from musify.remote.collection.playlist import RemotePlaylist
from musify.remote.item.track import RemoteTrack


class RemoteLibrary[TK, TV: RemoteTrack, KP, VP: RemotePlaylist](
    Library[TK, TV, KP, VP], metaclass=ABCMeta
):
    pass
