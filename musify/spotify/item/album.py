from typing import final, Any

from pydantic import field_validator

from musify.remote.item.album import RemoteAlbum
from musify.spotify._base import SpotifyResource
from musify.spotify.item.artist import SpotifyArtist
from musify.spotify.properties.followers import HasFollowers
from musify.spotify.properties.images import HasSpotifyImages
from musify.spotify.item.genre import SpotifyGenre
from musify.spotify.properties.popularity import HasPopularity
from musify.spotify.properties.uri import SpotifyResourceURI


@final
class SpotifyAlbum(
    RemoteAlbum[SpotifyResourceURI, SpotifyArtist, SpotifyGenre],
    SpotifyResource[SpotifyResourceURI],
    HasSpotifyImages,
    HasPopularity,
):
    __final__ = True

    uri: SpotifyResourceURI  # TODO: This shouldn't be needed...
