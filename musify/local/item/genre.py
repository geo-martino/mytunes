from typing import final

from musify.local._base import LocalResource
from musify.models.item.genre import Genre


@final
class LocalGenre(Genre, LocalResource):
    __final__ = True
