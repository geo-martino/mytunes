from typing import final

from musify.local._base import LocalResource
from musify.models.item.genre import Genre


@final
class LocalGenre(LocalResource, Genre):
    __final__ = True
