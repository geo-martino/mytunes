from typing import ClassVar, final

from pydantic import AliasPath
from yarl import URL

from mytunes.spotify import API_URL
from mytunes.spotify._api._base import SpotifyEndpoints, _SpotifyLibraryEndpoints
from .._collection.album import SpotifyAlbumCollection
from .._item.track import SpotifyTrack
from .._properties.uri import SpotifyResourceURI
from ...core.api import HasLibraryEndpoints, ItemReadEndpoints, ItemsReadEndpoints, ItemReadAllEndpoints, \
    CollectionReadEndpoints, BatchWriteEndpoints


@final
class _SpotifyAlbumLibraryEndpoints(
    _SpotifyLibraryEndpoints[SpotifyResourceURI, SpotifyAlbumCollection],
    ItemReadAllEndpoints[SpotifyResourceURI, SpotifyAlbumCollection],
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
    SpotifyEndpoints[SpotifyResourceURI, SpotifyAlbumCollection],
    HasLibraryEndpoints[_SpotifyAlbumLibraryEndpoints],
    ItemReadEndpoints[SpotifyResourceURI, SpotifyAlbumCollection],
    ItemsReadEndpoints[SpotifyResourceURI, SpotifyAlbumCollection],
    CollectionReadEndpoints[SpotifyResourceURI, SpotifyAlbumCollection, SpotifyTrack],
):
    __final__ = True

    _extend_path: ClassVar[str] = "items"
