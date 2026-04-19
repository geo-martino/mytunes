from typing import final

from mytunes.local._collection._base import LocalCollection
from .._item.genre import LocalGenre
from .._item.track import LocalTrack, HasLocalTracks
from ..._models.collection.genre import GenreCollection
from ..._models.properties.uri import URI


# noinspection PyFinal
@final
class LocalGenreCollection[TT: LocalTrack](
    HasLocalTracks[TT], GenreCollection[TT], LocalGenre, LocalCollection[TT]
):
    __final__ = True
