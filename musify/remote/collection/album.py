from musify.models.collection.album import AlbumCollection
from musify.models.properties.uri import URI
from musify.remote._base import RemoteResource
from musify.remote.collection._base import RemoteCollection
from musify.remote.item.album import RemoteAlbum
from musify.remote.item.artist import RemoteArtist
from musify.remote.item.genre import RemoteGenre
from musify.remote.item.track import RemoteTrack


class RemoteAlbumCollection[TK, TV: RemoteTrack, RT: RemoteArtist, GT: RemoteGenre, UT: URI](
    AlbumCollection[TK, TV, RT, GT, UT], RemoteAlbum[UT, RT, GT], RemoteResource[UT], RemoteCollection
):
    pass
