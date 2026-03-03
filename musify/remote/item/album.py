from musify.models.item.album import Album
from musify.models.properties.uri import URI
from musify.remote._base import RemoteResource
from musify.remote.item.artist import RemoteArtist
from musify.remote.item.genre import RemoteGenre


class RemoteAlbum[UT: URI, RT: RemoteArtist, GT: RemoteGenre](RemoteResource[UT], Album[RT, GT]):
    pass
