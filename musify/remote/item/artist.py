from musify.models.item.artist import Artist
from musify.models.properties.uri import URI
from musify.remote._base import RemoteResource
from musify.remote.item.genre import RemoteGenre


class RemoteArtist[GT: RemoteGenre, UT: URI](Artist[GT, UT], RemoteResource[UT]):
    pass
