from typing import ClassVar, final, Any

from pydantic import PositiveInt, validate_call, AliasPath
from yarl import URL

from musify.models import ResourceModel
from musify.models.api.search import SearchEndpoints
from musify.models.collection.playlist import Playlist
from musify.models.item.album import Album
from musify.models.item.artist import Artist
from musify.models.item.track import Track
from musify.spotify import API_URL, SpotifyResource
from musify.spotify.api._base import SpotifyEndpoints
from musify.spotify.collection.playlist import SpotifyPlaylist
from musify.spotify.item.album import SpotifyAlbum
from musify.spotify.item.artist import SpotifyArtist
from musify.spotify.item.track import SpotifyTrack
from musify.spotify.properties.uri import SpotifyResourceURI


@final
class SpotifySearchEndpoints(
    SpotifyEndpoints[SpotifyResourceURI, SpotifyTrack | SpotifyAlbum | SpotifyArtist | SpotifyPlaylist],
    SearchEndpoints[SpotifyResourceURI, SpotifyTrack | SpotifyAlbum | SpotifyArtist | SpotifyPlaylist],
):
    __final__ = True

    _query_url: ClassVar[URL] = API_URL.joinpath("search")
    _query_path: ClassVar[AliasPath] = AliasPath("{type}s", "items")
    _query_limit: ClassVar[int] = 10

    @classmethod
    @validate_call
    def _format_query_params(
            cls,
            query: str,
            types: set[str | type[Track] | type[Album] | type[Artist] | type[Playlist]],
            limit: PositiveInt | None = None,
            offset: PositiveInt | None = None,
    ) -> dict[str, Any]:
        types_mapped = map(cls._map_type_to_str, types)

        params: dict[str, Any] = {"q": query, "type": ",".join(types_mapped)}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset

        return params

    @classmethod
    @validate_call
    def _format_query_from_item(cls, item: ResourceModel, **kwargs) -> dict[str, Any]:
        match item:
            case Track() as track if track.artists:
                query = f"track:{track.name} artist:{track.artists[0].name}"
            case Track() as track:
                query = track.name
            case Album() as album if album.artists:
                query = f"album:{album.name} artist:{album.artists[0].name}"
            case Album() as album:
                query = album.name
            case Artist() as artist:
                query = artist.name
            case Playlist() as playlist:
                query = playlist.name
            case _:
                raise ValueError(f"Unsupported item type: {item.type}")

        item_type = item if isinstance(item, SpotifyResource) else item.type
        return {"query": query, "types": {item_type}} | kwargs
