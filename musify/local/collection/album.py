from typing import final

from musify.local.collection._base import LocalCollection
from musify.local.item.album import LocalAlbum
from musify.local.item.artist import LocalArtist
from musify.local.item.genre import LocalGenre
from musify.local.item.track import LocalTrack, HasLocalTracks
from musify.models.collection.album import AlbumCollection
from musify.models.properties.uri import URI


# noinspection PyFinal
@final
class LocalAlbumCollection[TT: LocalTrack, RT: LocalArtist, GT: LocalGenre](
    HasLocalTracks[URI, TT], AlbumCollection[URI, TT, RT, GT, URI], LocalAlbum[RT, GT], LocalCollection[TT]
):
    __final__ = True
