from musify.remote.item.album import RemoteAlbum
from musify.spotify._base import SpotifyResource
from musify.spotify.item.artist import SpotifyArtist
from musify.spotify.properties.followers import HasFollowers
from musify.spotify.properties.images import HasSpotifyImages
from musify.spotify.item.genre import SpotifyGenre
from musify.spotify.properties.popularity import HasPopularity
from musify.spotify.properties.uri import SpotifyResourceURI


class SpotifyAlbum(
    SpotifyResource[SpotifyResourceURI],
    RemoteAlbum[SpotifyResourceURI, SpotifyArtist, SpotifyGenre],
    HasSpotifyImages,
    HasFollowers,
    HasPopularity
):
    uri: SpotifyResourceURI  # TODO: This shouldn't be needed...
