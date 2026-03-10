from typing import final

from musify.local.collection._base import LocalCollection
from musify.local.item.album import LocalAlbum
from musify.local.item.artist import LocalArtist
from musify.local.item.genre import LocalGenre
from musify.local.item.track import LocalTrack
from musify.models.collection.artist import ArtistCollection
from musify.models.properties.uri import URI


# noinspection PyFinal
@final
class LocalArtistCollection[TT: LocalTrack, AT: LocalAlbum, GT: LocalGenre](
    ArtistCollection[URI, TT, AT, GT, URI], LocalArtist[GT], LocalCollection[AT]
):
    __final__ = True
