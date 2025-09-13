from musify.local.collection._base import LocalCollection
from musify.local.item.album import LocalAlbum
from musify.local.item.artist import LocalArtist
from musify.local.item.genre import LocalGenre
from musify.local.item.track import LocalTrack
from musify.models.collection.album import AlbumCollection


class LocalAlbumCollection[TK, TV: LocalTrack, RT: LocalArtist, GT: LocalGenre](
    LocalCollection, LocalAlbum[RT, GT], AlbumCollection[TK, TV, RT, GT]
):
    pass
