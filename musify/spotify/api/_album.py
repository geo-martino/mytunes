from typing import ClassVar, final, Type

from pydantic import AliasPath
from yarl import URL

from musify.models.api import HasLibraryEndpoints
from musify.models.api.album import AlbumReadEndpoints, AlbumBatchReadEndpoints, \
    AlbumBatchReadAllEndpoints, AlbumBatchWriteEndpoints, AlbumCollectionReadEndpoints
from musify.spotify import API_URL
from musify.spotify.api._base import SpotifyEndpoints, _SpotifyLibraryEndpoints
from musify.spotify.collection.album import SpotifyAlbumCollection
from musify.spotify.item.album import SpotifyAlbum
from musify.spotify.item.track import SpotifyTrack
from musify.spotify.properties.uri import SpotifyResourceURI


@final
class _SpotifyAlbumLibraryEndpoints(
    _SpotifyLibraryEndpoints[SpotifyResourceURI, SpotifyAlbum],
    AlbumBatchReadAllEndpoints[SpotifyResourceURI, SpotifyAlbum],
    AlbumBatchWriteEndpoints[SpotifyResourceURI, SpotifyAlbum],
):
    __final__ = True

    type: ClassVar[Type] = SpotifyAlbumCollection  # override to force creation of collections from responses

    _read_all_url: ClassVar[URL] = API_URL.joinpath("me/albums")
    _read_all_limit: ClassVar[int] = 50
    _read_all_path: ClassVar[AliasPath] = AliasPath("items", "*", "album")

    _write_url: ClassVar[URL] = API_URL.joinpath("me/library")
    _write_limit: ClassVar[int] = 40


@final
class SpotifyAlbumEndpoints(
    SpotifyEndpoints[SpotifyResourceURI, SpotifyAlbum],
    HasLibraryEndpoints[_SpotifyAlbumLibraryEndpoints],
    AlbumReadEndpoints[SpotifyResourceURI, SpotifyAlbum],
    AlbumBatchReadEndpoints[SpotifyResourceURI, SpotifyAlbum],
    AlbumCollectionReadEndpoints[SpotifyResourceURI, SpotifyAlbumCollection, SpotifyTrack],
):
    __final__ = True

    _read_url: ClassVar[URL] = API_URL.joinpath("albums")
    _read_limit: ClassVar[int] = 20
    _read_path: ClassVar[str] = "albums"

    _extend_path: ClassVar[str] = "items"
