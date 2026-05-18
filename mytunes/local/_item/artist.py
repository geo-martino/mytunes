from typing import final

from mytunes.core.artist import Artist
from mytunes.local._base import LocalModel
from mytunes.local._item.genre import LocalGenre


@final
class LocalArtist[GT: LocalGenre](Artist[GT], LocalModel):
    __final__ = True
