from typing import final

from mytunes.local._collection._base import LocalCollection
from .._item.album import LocalAlbum
from .._item.artist import LocalArtist
from .._item.genre import LocalGenre
from mytunes.core.artist import ArtistCollection


# noinspection PyFinal
@final
class LocalArtistCollection[AT: LocalAlbum, GT: LocalGenre](
    ArtistCollection[AT, GT], LocalArtist[GT], LocalCollection[AT]
):
    __final__ = True
