from musify.models.collection.artist import ArtistCollection
from musify.models.properties.uri import URI
from musify.remote._base import RemoteResource
from musify.remote.collection._base import RemoteCollection
from musify.remote.item.album import RemoteAlbum
from musify.remote.item.artist import RemoteArtist
from musify.remote.item.genre import RemoteGenre
from musify.remote.item.track import RemoteTrack


class RemoteArtistCollection[TK, TV: RemoteTrack, AT: RemoteAlbum, GT: RemoteGenre, UT: URI](
    ArtistCollection[TK, TV, AT, GT, UT],
    RemoteArtist[UT, GT],
    RemoteResource[UT],
    RemoteCollection,
):
    @property
    def _items(self) -> list:
        return self.albums
