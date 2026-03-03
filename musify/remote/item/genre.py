from musify.models.item.genre import Genre
from musify.models.properties.uri import URI
from musify.remote._base import RemoteResource


class RemoteGenre[UT: URI](RemoteResource[UT], Genre):
    pass
