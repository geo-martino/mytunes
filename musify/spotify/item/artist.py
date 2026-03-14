from typing import final

from musify.models.item.artist import RemoteArtist
from musify.spotify._base import SpotifyResource
from musify.spotify.item.genre import SpotifyGenre
from musify.spotify.properties.images import HasSpotifyImages
from musify.spotify.properties.stats import HasPopularity, HasFollowers
from musify.spotify.properties.uri import SpotifyResourceURI


@final
class SpotifyArtist(
    RemoteArtist[SpotifyGenre, SpotifyResourceURI],
    SpotifyResource[SpotifyResourceURI],
    HasSpotifyImages,
    HasFollowers,
    HasPopularity
):
    __final__ = True
