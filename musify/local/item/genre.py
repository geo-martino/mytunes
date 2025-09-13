from musify.local._base import LocalResource
from musify.models.item.genre import Genre


class LocalGenre(LocalResource, Genre):
    pass
