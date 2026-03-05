from typing import final

from musify.local.collection._base import LocalCollection
from musify.local.item.genre import LocalGenre
from musify.local.item.track import LocalTrack
from musify.models.collection.genre import GenreCollection


@final
class LocalGenreCollection[TK, TV: LocalTrack](
    GenreCollection[TK, TV], LocalGenre, LocalCollection
):
    __final__ = True
