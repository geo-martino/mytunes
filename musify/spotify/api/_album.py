from typing import ClassVar, final

from pydantic import AliasPath
from yarl import URL

from musify.models.api import HasLibraryEndpoints, BatchReadAllEndpoints, BatchWriteEndpoints, BatchReadEndpoints, \
    ItemReadEndpoints, CollectionReadEndpoints
from musify.spotify import API_URL
from musify.spotify.api._base import SpotifyEndpoints, _SpotifyLibraryEndpoints
from musify.spotify.collection.album import SpotifyAlbumCollection
from musify.spotify.item.album import SpotifyAlbum
from musify.spotify.item.track import SpotifyTrack
from musify.spotify.properties.uri import SpotifyResourceURI


@final
class _SpotifyAlbumLibraryEndpoints(
    _SpotifyLibraryEndpoints[SpotifyResourceURI, SpotifyAlbumCollection],
    BatchReadAllEndpoints[SpotifyResourceURI, SpotifyAlbumCollection],
    BatchWriteEndpoints[SpotifyResourceURI, SpotifyAlbumCollection],
):
    __final__ = True

    _read_all_url: ClassVar[URL] = API_URL.joinpath("me/albums")
    _read_all_limit: ClassVar[int] = 50
    _read_all_path: ClassVar[AliasPath] = AliasPath("items", "*", "album")

    _write_url: ClassVar[URL] = API_URL.joinpath("me/library")
    _write_limit: ClassVar[int] = 40


@final
class SpotifyAlbumEndpoints(
    SpotifyEndpoints[SpotifyResourceURI, SpotifyAlbum],
    HasLibraryEndpoints[_SpotifyAlbumLibraryEndpoints],
    ItemReadEndpoints[SpotifyResourceURI, SpotifyAlbum],
    BatchReadEndpoints[SpotifyResourceURI, SpotifyAlbum],
    CollectionReadEndpoints[SpotifyResourceURI, SpotifyAlbumCollection, SpotifyTrack],
):
    __final__ = True

    _read_url: ClassVar[URL] = API_URL.joinpath("albums")
    _read_limit: ClassVar[int] = 20
    _read_path: ClassVar[str] = "albums"

    _extend_path: ClassVar[str] = "items"
