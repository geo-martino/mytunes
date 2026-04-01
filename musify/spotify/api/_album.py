from collections.abc import Iterable
from typing import ClassVar, final, Type, Any

from pydantic import AliasPath
from pydantic.json_schema import JsonSchemaValue
from yarl import URL

from musify.models.api import HasSavedEndpoints
from musify.models.api.album import AlbumReadItemEndpoints, AlbumReadItemsEndpoints, \
    AlbumReadSavedEndpoints, AlbumWriteSavedEndpoints, AlbumReadCollectionEndpoints
from musify.spotify import API_URL
from musify.spotify.api._base import SpotifyEndpoints
from musify.spotify.collection.album import SpotifyAlbumCollection
from musify.spotify.item.album import SpotifyAlbum
from musify.spotify.item.track import SpotifyTrack
from musify.spotify.properties.uri import SpotifyResourceURI


@final
class _SpotifySavedAlbumEndpoints(
    SpotifyEndpoints[SpotifyResourceURI, SpotifyAlbum],
    AlbumReadSavedEndpoints[SpotifyResourceURI, SpotifyAlbum],
    AlbumWriteSavedEndpoints[SpotifyResourceURI, SpotifyAlbum],
):
    __final__ = True

    type: ClassVar[Type] = SpotifyAlbumCollection  # override to force creation of collections from responses

    _read_url: ClassVar[URL] = API_URL.joinpath("me/albums")
    _read_limit: ClassVar[int] = 50
    _read_path: ClassVar[AliasPath] = AliasPath("items", "*", "album")

    _write_url: ClassVar[URL] = API_URL.joinpath("me/library")
    _write_limit: ClassVar[int] = 40

    @staticmethod
    def _generate_add_batch_kwargs(values: Iterable[Any]) -> JsonSchemaValue:
        return {"params": {"uris": ",".join(map(str, values))}}

    @staticmethod
    def _generate_remove_batch_kwargs(values: Iterable[Any]) -> JsonSchemaValue:
        return {"params": {"uris": ",".join(map(str, values))}}


@final
class SpotifyAlbumEndpoints(
    SpotifyEndpoints[SpotifyResourceURI, SpotifyAlbum],
    HasSavedEndpoints[_SpotifySavedAlbumEndpoints],
    AlbumReadItemEndpoints[SpotifyResourceURI, SpotifyAlbum],
    AlbumReadItemsEndpoints[SpotifyResourceURI, SpotifyAlbum],
    AlbumReadCollectionEndpoints[SpotifyResourceURI, SpotifyAlbumCollection, SpotifyTrack],
):
    __final__ = True

    _many_url: ClassVar[URL] = API_URL.joinpath("albums")
    _many_limit: ClassVar[int] = 20
    _many_path: ClassVar[str] = "albums"

    _extend_path: ClassVar[str] = "items"
