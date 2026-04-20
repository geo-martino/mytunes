from typing import final

from mytunes.local._collection._base import LocalCollection
from .._item.album import LocalAlbum
from .._item.artist import LocalArtist
from .._item.genre import LocalGenre
from .._item.track import LocalTrack, HasLocalTracks
from mytunes.core.album import AlbumCollection


# noinspection PyFinal
@final
class LocalAlbumCollection[TT: LocalTrack, RT: LocalArtist, GT: LocalGenre](
    HasLocalTracks[TT],
    AlbumCollection[TT, RT, GT],
    LocalAlbum[RT, GT],
    LocalCollection[TT]
):
    __final__ = True
