from typing import final

from musify.local._collection._base import LocalCollection
from musify.models.collection.genre import GenreCollection
from musify.models.properties.uri import URI
from .._item.genre import LocalGenre
from .._item.track import LocalTrack, HasLocalTracks


# noinspection PyFinal
@final
class LocalGenreCollection[TT: LocalTrack](
    HasLocalTracks[URI, TT], GenreCollection[URI, TT], LocalGenre, LocalCollection[TT]
):
    __final__ = True
