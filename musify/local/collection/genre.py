from musify.local.item.album import LocalAlbum
from musify.local.item.artist import LocalArtist
from musify.local.item.genre import LocalGenre
from musify.local.item.track import LocalTrack
from musify.model.collection.artist import ArtistCollection
from musify.model.collection.genre import GenreCollection


class LocalGenreCollection[TK, TV: LocalTrack](
    LocalGenre, GenreCollection[TK, TV]
):
    pass
