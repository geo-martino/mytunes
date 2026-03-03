from musify.models.item.genre import Genre
from musify.remote._base import RemoteResource


class RemoteGenre(RemoteResource, Genre):
    pass
