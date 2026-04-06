from typing import final

from musify.spotify._base import SpotifyResource
from musify.spotify._item.genre import SpotifyGenre
from .._properties.images import HasSpotifyImages
from .._properties.rating import HasSpotifyRating
from .._properties.stats import HasFollowers
from .._properties.uri import SpotifyResourceURI
from ..._models.item.artist import RemoteArtist


@final
class SpotifyArtist(
    SpotifyResource[SpotifyResourceURI],
    HasSpotifyImages,
    HasSpotifyRating,
    HasFollowers,
    RemoteArtist[SpotifyResourceURI, SpotifyGenre],
):
    __final__ = True
