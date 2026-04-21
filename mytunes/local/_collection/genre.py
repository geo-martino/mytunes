from typing import final

from mytunes.core.genre import GenreCollection
from mytunes.local._collection._base import LocalCollection

from .._item.genre import LocalGenre
from .._item.track import LocalTrack, HasLocalTracks


# noinspection PyFinal
@final
class LocalGenreCollection[TT: LocalTrack](
    HasLocalTracks[TT], GenreCollection[TT], LocalGenre, LocalCollection[TT]
):
    __final__ = True
