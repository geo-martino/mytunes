from typing import final

from musify.local._base import LocalModel
from musify.models.item.genre import Genre


@final
class LocalGenre(Genre, LocalModel):
    __final__ = True
