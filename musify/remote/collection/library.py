from musify.models.collection.library import Library, MutableLibrary
from musify.remote import RemoteModel
from musify.remote.collection.playlist import RemotePlaylist
from musify.remote.item.track import RemoteTrack


# noinspection PyAbstractClass
class RemoteLibrary[TK, TV: RemoteTrack, KP, VP: RemotePlaylist](
    Library[TK, TV, KP, VP], RemoteModel
):
    pass


# noinspection PyAbstractClass
class RemoteMutableLibrary[TK, TV: RemoteTrack, KP, VP: RemotePlaylist](
    MutableLibrary[TK, TV, KP, VP], RemoteLibrary[TK, TV, KP, VP]
):
    pass
