from typing import final

from musify.local.collection._base import LocalCollection
from musify.local.item.album import LocalAlbum
from musify.local.item.artist import LocalArtist
from musify.local.item.genre import LocalGenre
from musify.local.item.track import LocalTrack
from musify.models.collection.artist import ArtistCollection


@final
class LocalArtistCollection[TK, TV: LocalTrack, AT: LocalAlbum, GT: LocalGenre](
    LocalCollection, LocalArtist[GT], ArtistCollection[TK, TV, AT, GT]
):
    __final__ = True
