from typing import final

from mytunes.local._base import LocalModel
from ..._models.item.genre import Genre


@final
class LocalGenre(Genre, LocalModel):
    __final__ = True
