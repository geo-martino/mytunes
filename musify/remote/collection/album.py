from musify.models.collection.album import AlbumCollection
from musify.models.properties.uri import URI
from musify.remote._base import RemoteResource
from musify.remote.collection._base import RemoteCollection
from musify.remote.item.album import RemoteAlbum
from musify.remote.item.artist import RemoteArtist
from musify.remote.item.genre import RemoteGenre
from musify.remote.item.track import RemoteTrack


class RemoteAlbumCollection[TK, TV: RemoteTrack, UT: URI, RT: RemoteArtist, GT: RemoteGenre](
    AlbumCollection[TK, TV, RT, GT], RemoteResource[UT], RemoteCollection, RemoteAlbum[UT, RT, GT]
):
    pass
