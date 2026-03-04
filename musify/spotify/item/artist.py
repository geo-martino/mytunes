from typing import Any

from pydantic import Field, PositiveInt, AliasPath, field_validator, Json

from musify.remote.item.artist import RemoteArtist
from musify.spotify._base import SpotifyResource
from musify.spotify.properties.followers import HasFollowers
from musify.spotify.properties.images import HasSpotifyImages
from musify.spotify.item.genre import SpotifyGenre
from musify.spotify.properties.popularity import HasPopularity
from musify.spotify.properties.uri import SpotifyResourceURI


class SpotifyArtist(
    RemoteArtist[SpotifyResourceURI, SpotifyGenre],
    SpotifyResource[SpotifyResourceURI],
    HasSpotifyImages,
    HasFollowers,
    HasPopularity
):
    uri: SpotifyResourceURI  # TODO: This shouldn't be needed...
