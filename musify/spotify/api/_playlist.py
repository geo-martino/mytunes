from collections.abc import Iterable, Sequence
from typing import ClassVar, final, Annotated

from aiorequestful.types import JSON
from pydantic import validate_call, PositiveInt, Field
from yarl import URL

from musify.remote.api._types import ApiURISchema, ApiURLSchema
from musify.remote.api.playlist import PlaylistMutableEndpoints, \
    PlaylistMutableSavedEndpoints
from musify.spotify import API_URL
from musify.spotify.api._base import SpotifyEndpoints
from musify.spotify.collection.playlist import SpotifyPlaylist, SpotifyMutablePlaylist
from musify.spotify.item.track import SpotifyTrack
from musify.spotify.properties.uri import SpotifyResourceURI
from musify.spotify.user import SpotifyUser


@final
class _SpotifySavedPlaylistEndpoints(
    SpotifyEndpoints[SpotifyResourceURI, SpotifyPlaylist],
    PlaylistMutableSavedEndpoints[SpotifyResourceURI, SpotifyMutablePlaylist, SpotifyUser],
):
    __final__ = True

    _saved_url: ClassVar[URL] = API_URL.joinpath("me/playlists")
    _saved_limit: ClassVar[int] = 50
    _saved_path: ClassVar[str] = "items"

    @validate_call
    async def create(
            self, name: str, public: bool = None, collaborative: bool = None, description: str = None
    ) -> SpotifyPlaylist:
        body: JSON = {"name": name}
        if public is not None:
            body["public"] = public
        if collaborative is not None:
            body["collaborative"] = collaborative
        if description is not None:
            body["description"] = description

        return await super().create(**body)


@final
class SpotifyPlaylistEndpoints(
    SpotifyEndpoints[SpotifyResourceURI, SpotifyMutablePlaylist],
    PlaylistMutableEndpoints[SpotifyResourceURI, SpotifyMutablePlaylist],
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
            url: Annotated[URL, ApiURLSchema[SpotifyResourceURI, SpotifyMutablePlaylist]],
            uris: Sequence[Annotated[SpotifyResourceURI, ApiURISchema[SpotifyResourceURI, SpotifyTrack]]],
            limit: PositiveInt = None
    ) -> int:
        return await super().append(url.joinpath("items"), uris=uris, limit=limit)

    # WORKAROUND: Replace decorator with validate_call when this issue is resolved:
    # https://github.com/pydantic/pydantic/issues/7796
    @ApiURLSchema.validate_call
    @ApiURISchema.validate_call
    async def remove(
            self,
            url: Annotated[URL, ApiURLSchema[SpotifyResourceURI, SpotifyMutablePlaylist]],
            uris: Sequence[Annotated[SpotifyResourceURI, ApiURISchema[SpotifyResourceURI, SpotifyTrack]]],
            limit: PositiveInt = None
    ) -> int:
        return await super().remove(url.joinpath("items"), uris=uris, limit=limit)

    @staticmethod
    def _generate_remove_batch_body(values: Iterable[str]) -> JSON:
        return {"items": [{"uri": str(uri)} for uri in values]}
