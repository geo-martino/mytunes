from musify.models.item.artist import Artist
from musify.remote._base import RemoteResource
from musify.remote.item.genre import RemoteGenre


class RemoteArtist[GT: RemoteGenre](RemoteResource, Artist[GT]):
    pass
