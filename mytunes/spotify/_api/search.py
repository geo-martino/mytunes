from typing import ClassVar, final, Any

from pydantic import PositiveInt, validate_call, AliasPath
from yarl import URL

from mytunes.exception import RequestError
from mytunes.spotify import API_URL, SpotifyResource
from mytunes.spotify._api._base import SpotifyEndpoints
from .._collection.playlist import SpotifyPlaylist
from .._item.album import SpotifyAlbum
from .._item.artist import SpotifyArtist
from .._item.track import SpotifyTrack
from .._properties.uri import SpotifyResourceURI
from ..._base.resource import ResourceModel
from ...core.api.search import SearchEndpoints
from mytunes.core.playlist import Playlist
from mytunes.core.album import Album
from mytunes.core.artist import Artist
from mytunes.core.track import Track

type _SearchT = Track | Album | Artist | Playlist
type _ReturnT = SpotifyTrack | SpotifyAlbum | SpotifyArtist | SpotifyPlaylist


@final
class SpotifySearchEndpoints(
    SpotifyEndpoints[SpotifyResourceURI, _ReturnT],
    SearchEndpoints[SpotifyResourceURI, _ReturnT, _SearchT],
):
    __final__ = True

    _query_url: ClassVar[URL] = API_URL.joinpath("search")
    _query_path: ClassVar[AliasPath] = AliasPath("{type}s", "items")
    _query_limit: ClassVar[int] = 10

    @validate_call
    def _format_query_params(
            self,
            query: str,
            types: set[str],
            limit: PositiveInt | None = None,
            offset: PositiveInt | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"q": query, "type": ",".join(types)}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset

        return params

    @validate_call
    def _format_query_from_item(self, item: _SearchT, **kwargs) -> dict[str, Any]:
        match item:
            case Track() as track if track.artists:
                query = f"track:{self._get_name(track)} artist:{self._get_name(track.artists[0])}"
            case Track() as track:
                query = self._get_name(track)
            case Album() as album if album.artists:
                query = f"album:{self._get_name(album)} artist:{self._get_name(album.artists[0])}"
            case Album() as album:
                query = self._get_name(album)
            case Artist() as artist:
                query = self._get_name(artist)
            case Playlist() as playlist:
                query = self._get_name(playlist)
            case ResourceModel() as resource:
                raise RequestError(f"Unsupported item type: {resource.type!r}")
            case _:
                raise RequestError(f"Unsupported item type: {type(item).__name__!r}")

        item_type = type(item) if isinstance(item, SpotifyResource) else item.type
        return {"query": query, "types": {item_type}} | kwargs
