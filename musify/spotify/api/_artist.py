from typing import ClassVar, final

from pydantic import AliasPath, Field
from yarl import URL

from musify.remote.api.artist import ArtistGetSingleEndpoints, ArtistGetManyEndpoints, \
    ArtistGetSavedEndpoints, ArtistCollectionEndpoints, ArtistMutableSavedEndpoints
from musify.spotify import API_URL
from musify.spotify.api._base import SpotifyEndpoints
from musify.spotify.collection.artist import SpotifyArtistCollection
from musify.spotify.item.artist import SpotifyArtist
from musify.spotify.properties.uri import SpotifyResourceURI


@final
class _SpotifySavedArtistEndpoints(
    SpotifyEndpoints[SpotifyResourceURI, SpotifyArtist],
    ArtistGetSavedEndpoints[SpotifyResourceURI, SpotifyArtist],
    ArtistMutableSavedEndpoints[SpotifyResourceURI, SpotifyArtist],
):
    __final__ = True

    _saved_url: ClassVar[URL] = API_URL.joinpath("me/following").with_query(type="artist")
    _saved_limit: ClassVar[int] = 50
    _saved_path: ClassVar[AliasPath] = AliasPath("artists", "items")

    _batch_limit: ClassVar[int] = 50


@final
class SpotifyArtistEndpoints(
    SpotifyEndpoints[SpotifyResourceURI, SpotifyArtist],
    ArtistGetSingleEndpoints[SpotifyResourceURI, SpotifyArtist],
    ArtistGetManyEndpoints[SpotifyResourceURI, SpotifyArtist],
    ArtistCollectionEndpoints[SpotifyResourceURI, SpotifyArtistCollection],
):
    __final__ = True

    _many_url: ClassVar[URL] = API_URL.joinpath("artists")
    _many_limit: ClassVar[int] = 50
    _many_path: ClassVar[str] = "artists"

    _extend_path: ClassVar[str] = "items"

    following: _SpotifySavedArtistEndpoints = Field(
        description="Access endpoints for the current user's followed artist.",
    )
