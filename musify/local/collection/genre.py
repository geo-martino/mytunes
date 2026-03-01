from typing import final

from musify.local.collection._base import LocalCollection
from musify.local.item.genre import LocalGenre
from musify.local.item.track import LocalTrack
from musify.models.collection.genre import GenreCollection


@final
class LocalGenreCollection[TK, TV: LocalTrack](
    LocalCollection, LocalGenre, GenreCollection[TK, TV]
):
    __final__ = True
