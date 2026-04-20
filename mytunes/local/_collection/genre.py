from typing import final

from mytunes.local._collection._base import LocalCollection
from .._item.genre import LocalGenre
from .._item.track import LocalTrack, HasLocalTracks
from mytunes.core.genre import GenreCollection


# noinspection PyFinal
@final
class LocalGenreCollection[TT: LocalTrack](
    HasLocalTracks[TT], GenreCollection[TT], LocalGenre, LocalCollection[TT]
):
    __final__ = True
