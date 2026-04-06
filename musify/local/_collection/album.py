from typing import final

from musify.local._collection._base import LocalCollection
from musify.models.collection.album import AlbumCollection
from musify.models.properties.uri import URI
from .._item.album import LocalAlbum
from .._item.artist import LocalArtist
from .._item.genre import LocalGenre
from .._item.track import LocalTrack, HasLocalTracks


# noinspection PyFinal
@final
class LocalAlbumCollection[TT: LocalTrack, RT: LocalArtist, GT: LocalGenre](
    HasLocalTracks[URI, TT],
    AlbumCollection[URI, TT, RT, GT],
    LocalAlbum[RT, GT],
    LocalCollection[TT]
):
    __final__ = True
