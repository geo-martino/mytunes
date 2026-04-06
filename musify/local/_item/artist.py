from typing import final

from musify.local._base import LocalModel
from musify.local._item.genre import LocalGenre
from ..._models.item.artist import Artist


@final
class LocalArtist[GT: LocalGenre](Artist[GT], LocalModel):
    __final__ = True
