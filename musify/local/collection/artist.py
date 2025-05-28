from musify.local.item.album import LocalAlbum
from musify.local.item.artist import LocalArtist
from musify.local.item.genre import LocalGenre
from musify.local.item.track import LocalTrack
from musify.model.collection.artist import ArtistCollection


class LocalArtistCollection[TK, TV: LocalTrack, AT: LocalAlbum, GT: LocalGenre](
    LocalArtist[GT], ArtistCollection[TK, TV, AT, GT]
):
    pass
