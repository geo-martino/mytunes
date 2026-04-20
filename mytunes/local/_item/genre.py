from typing import final

from mytunes.core.genre import Genre
from mytunes.local._base import LocalModel


@final
class LocalGenre(Genre, LocalModel):
    __final__ = True
