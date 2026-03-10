from collections.abc import Iterable
from typing import ClassVar, final

from aiorequestful.types import JSON
from pydantic import validate_call, PositiveInt, Field
from yarl import URL

from musify.remote.api.playlist import PlaylistReadWriteEndpoints, PlaylistReadWriteSavedEndpoints
from musify.remote.api.types import ApiURISchema, ApiURLSchema
from musify.spotify import API_URL
from musify.spotify.api._base import SpotifyEndpoints
from musify.spotify.api._types import SpotifyApiURL, SpotifyApiURISequence
from musify.spotify.collection.playlist import SpotifyPlaylist, SpotifyMutablePlaylist
from musify.spotify.item.track import SpotifyTrack
from musify.spotify.properties.uri import SpotifyResourceURI
from musify.spotify.user import SpotifyUser


@final
class _SpotifySavedPlaylistEndpoints(
    SpotifyEndpoints[SpotifyResourceURI, SpotifyPlaylist],
    PlaylistReadWriteSavedEndpoints[SpotifyResourceURI, SpotifyMutablePlaylist, SpotifyUser],
):
    __final__ = True

    _saved_url: ClassVar[URL] = API_URL.joinpath("me/playlists")
    _saved_limit: ClassVar[int] = 50
    _saved_path: ClassVar[str] = "items"

    @staticmethod
    @validate_call
    def _format_playlist_body(
            name: str = None, public: bool = None, collaborative: bool = None, description: str = None
    ) -> JSON:
        body: JSON = {}
        if name is not None:
            body["name"] = name
        if public is not None:
            body["public"] = public
        if collaborative is not None:
            body["collaborative"] = collaborative
        if description is not None:
            body["description"] = description

        return body

    @validate_call
    async def create(self, name: str, **kwargs) -> SpotifyPlaylist:
        body = self._format_playlist_body(name=name, **kwargs)
        return await super().create(**body)

    # WORKAROUND: Replace decorator with validate_call when this issue is resolved:
    # https://github.com/pydantic/pydantic/issues/7796
    @ApiURLSchema.validate_call
    async def follow(self, url: SpotifyApiURL[SpotifyPlaylist], **kwargs) -> None:
        return await super().follow(url.joinpath("followers"))

    # WORKAROUND: Replace decorator with validate_call when this issue is resolved:
    # https://github.com/pydantic/pydantic/issues/7796
    @ApiURLSchema.validate_call
    async def modify(self, url: SpotifyApiURL[SpotifyPlaylist], **kwargs) -> None:
        body = self._format_playlist_body(**kwargs)
        return await super().create(**body)

    # WORKAROUND: Replace decorator with validate_call when this issue is resolved:
    # https://github.com/pydantic/pydantic/issues/7796
    @ApiURLSchema.validate_call
    async def delete(self, url: SpotifyApiURL[SpotifyPlaylist], **kwargs) -> None:
        return await super().delete(url.joinpath("followers"))


@final
class SpotifyPlaylistEndpoints(
    SpotifyEndpoints[SpotifyResourceURI, SpotifyMutablePlaylist],
    PlaylistReadWriteEndpoints[SpotifyResourceURI, SpotifyMutablePlaylist],
):
    __final__ = True

    _batch_limit: ClassVar[int] = 100
    _extend_path: ClassVar[str] = "items"

    saved: _SpotifySavedPlaylistEndpoints = Field(
        description="Access endpoints for the current user's saved playlists.",
    )

    # WORKAROUND: Replace decorator with validate_call when this issue is resolved:
    # https://github.com/pydantic/pydantic/issues/7796
    @ApiURLSchema.validate_call
    @ApiURISchema.validate_call
    async def append(
            self,
            url: SpotifyApiURL[SpotifyMutablePlaylist],
            uris: SpotifyApiURISequence[SpotifyTrack],
            limit: PositiveInt = None
    ) -> int:
        return await super().append(url.joinpath("items"), uris=uris, limit=limit)

    # WORKAROUND: Replace decorator with validate_call when this issue is resolved:
    # https://github.com/pydantic/pydantic/issues/7796
    @ApiURLSchema.validate_call
    @ApiURISchema.validate_call
    async def remove(
            self,
            url: SpotifyApiURL[SpotifyMutablePlaylist],
            uris: SpotifyApiURISequence[SpotifyTrack],
            limit: PositiveInt = None
    ) -> int:
        return await super().remove(url.joinpath("items"), uris=uris, limit=limit)

    @staticmethod
    def _generate_remove_batch_body(values: Iterable[str]) -> JSON:
        return {"items": [{"uri": str(uri)} for uri in values]}
