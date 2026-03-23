from typing import final

from musify.local.collection._base import LocalCollection
from musify.local.item.album import LocalAlbum
from musify.local.item.artist import LocalArtist
from musify.local.item.genre import LocalGenre
from musify.models.collection.artist import ArtistCollection


# noinspection PyFinal
@final
class LocalArtistCollection[AT: LocalAlbum, GT: LocalGenre](
    ArtistCollection[AT, GT], LocalArtist[GT], LocalCollection[AT]
):
    __final__ = True
