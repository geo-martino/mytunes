from abc import ABCMeta

from musify.models.collection.library import Library
from musify.models.properties.uri import URI
from musify.remote.collection._base import RemoteCollection
from musify.remote.collection.playlist import RemotePlaylist
from musify.remote.item.track import RemoteTrack


class RemoteLibrary[TK, TV: RemoteTrack, KP, VP: RemotePlaylist, UT: URI](
    RemoteCollection[UT], Library[TK, TV, KP, VP], metaclass=ABCMeta
):
    pass
