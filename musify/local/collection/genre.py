from typing import final

from musify.local.collection._base import LocalCollection
from musify.local.item.genre import LocalGenre
from musify.local.item.track import LocalTrack
from musify.models.collection.genre import GenreCollection
from musify.models.properties.uri import URI


# noinspection PyFinal
@final
class LocalGenreCollection[TT: LocalTrack](
    GenreCollection[URI, TT], LocalGenre, LocalCollection
):
    __final__ = True
