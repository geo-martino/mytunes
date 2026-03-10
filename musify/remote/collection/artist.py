from musify.models.collection.artist import ArtistCollection
from musify.models.properties.uri import URI
from musify.remote._base import RemoteResource
from musify.remote.collection._base import RemoteCollection, ItemsCursor
from musify.remote.item.album import RemoteAlbum
from musify.remote.item.artist import RemoteArtist
from musify.remote.item.genre import RemoteGenre
from musify.remote.item.track import RemoteTrack


class RemoteArtistCollection[TK, TV: RemoteTrack, AT: RemoteAlbum, GT: RemoteGenre, UT: URI, CT: ItemsCursor](
    ArtistCollection[TK, TV, AT, GT, UT],
    RemoteArtist[UT, GT],
    RemoteResource[UT],
    RemoteCollection[AT, CT],
):
    pass
