from typing import final

from musify.models.item.artist import RemoteArtist
from musify.spotify._base import SpotifyResource
from musify.spotify.item.genre import SpotifyGenre
from musify.spotify.properties.images import HasSpotifyImages
from musify.spotify.properties.rating import HasSpotifyRating
from musify.spotify.properties.stats import HasFollowers
from musify.spotify.properties.uri import SpotifyResourceURI


@final
class SpotifyArtist(
    SpotifyResource[SpotifyResourceURI],
    HasSpotifyImages,
    HasSpotifyRating,
    HasFollowers,
    RemoteArtist[SpotifyResourceURI, SpotifyGenre],
):
    __final__ = True
