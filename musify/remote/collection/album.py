from musify.models.collection.album import AlbumCollection
from musify.models.properties.uri import URI
from musify.models.sequence import MusifySequence
from musify.remote._base import RemoteResource
from musify.remote.collection._base import RemoteCollection, ItemsCursor
from musify.remote.item.album import RemoteAlbum
from musify.remote.item.artist import RemoteArtist
from musify.remote.item.genre import RemoteGenre
from musify.remote.item.track import RemoteTrack


class RemoteAlbumCollection[TT: RemoteTrack, RT: RemoteArtist, GT: RemoteGenre, UT: URI, CT: ItemsCursor](
    AlbumCollection[UT, TT, RT, GT, UT],
    RemoteAlbum[UT, RT, GT],
    RemoteResource[UT],
    RemoteCollection[TT, CT],
):
    pass
