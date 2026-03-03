from musify.models.collection.artist import ArtistCollection
from musify.models.properties.uri import URI
from musify.remote.collection._base import RemoteCollection
from musify.remote.item.album import RemoteAlbum
from musify.remote.item.artist import RemoteArtist
from musify.remote.item.genre import RemoteGenre
from musify.remote.item.track import RemoteTrack


class RemoteArtistCollection[TK, TV: RemoteTrack, UT: URI, AT: RemoteAlbum, GT: RemoteGenre](
    RemoteCollection[UT], RemoteArtist[UT, GT], ArtistCollection[TK, TV, AT, GT]
):
    pass
