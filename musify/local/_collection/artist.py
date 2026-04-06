from typing import final

from musify.local._collection._base import LocalCollection
from musify.models.collection.artist import ArtistCollection
from .._item.album import LocalAlbum
from .._item.artist import LocalArtist
from .._item.genre import LocalGenre


# noinspection PyFinal
@final
class LocalArtistCollection[AT: LocalAlbum, GT: LocalGenre](
    ArtistCollection[AT, GT], LocalArtist[GT], LocalCollection[AT]
):
    __final__ = True
