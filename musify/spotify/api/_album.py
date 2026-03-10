from typing import ClassVar, final

from pydantic import AliasPath, Field
from yarl import URL

from musify.remote.api.album import AlbumReadItemEndpoints, AlbumReadItemsEndpoints, \
    AlbumReadSavedEndpoints, AlbumWriteSavedEndpoints, AlbumReadCollectionEndpoints
from musify.spotify import API_URL
from musify.spotify.api._base import SpotifyEndpoints
from musify.spotify.collection.album import SpotifyAlbumCollection
from musify.spotify.item.album import SpotifyAlbum
from musify.spotify.properties.uri import SpotifyResourceURI


@final
class _SpotifySavedAlbumEndpoints(
    SpotifyEndpoints[SpotifyResourceURI, SpotifyAlbum],
    AlbumReadSavedEndpoints[SpotifyResourceURI, SpotifyAlbum],
    AlbumWriteSavedEndpoints[SpotifyResourceURI, SpotifyAlbum],
):
    __final__ = True

    _saved_url: ClassVar[URL] = API_URL.joinpath("me/albums")
    _saved_limit: ClassVar[int] = 50
    _saved_path: ClassVar[AliasPath] = AliasPath("items", "*", "album")

    _batch_limit: ClassVar[int] = 50


@final
class SpotifyAlbumEndpoints(
    SpotifyEndpoints[SpotifyResourceURI, SpotifyAlbum],
    AlbumReadItemEndpoints[SpotifyResourceURI, SpotifyAlbum],
    AlbumReadItemsEndpoints[SpotifyResourceURI, SpotifyAlbum],
    AlbumReadCollectionEndpoints[SpotifyResourceURI, SpotifyAlbumCollection],
):
    __final__ = True

    _many_url: ClassVar[URL] = API_URL.joinpath("albums")
    _many_limit: ClassVar[int] = 20
    _many_path: ClassVar[str] = "albums"

    _extend_path: ClassVar[str] = "items"

    saved: _SpotifySavedAlbumEndpoints = Field(
        description="Access endpoints for the current user's saved albums.",
    )
