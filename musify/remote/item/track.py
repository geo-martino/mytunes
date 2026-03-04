from musify.models.item.track import Track
from musify.models.properties.uri import URI
from musify.remote._base import RemoteResource
from musify.remote.item.album import RemoteAlbum
from musify.remote.item.artist import RemoteArtist
from musify.remote.item.genre import RemoteGenre


class RemoteTrack[UT: URI, RT: RemoteArtist, AT: RemoteAlbum, GT: RemoteGenre](
        Track[RT, AT, GT],
        RemoteResource[UT],
):
    pass
