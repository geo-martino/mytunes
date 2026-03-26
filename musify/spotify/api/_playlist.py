from collections.abc import Iterable
from typing import ClassVar, final, TYPE_CHECKING

from aiorequestful.response.exception import ResponseError
from aiorequestful.types import JSON
from pydantic import validate_call, PositiveInt, AliasPath, AliasChoices
from yarl import URL

from musify.local.item.track import LocalTrack
from musify.models.api import HasSavedEndpoints
from musify.models.api.playlist import PlaylistReadWriteEndpoints, PlaylistReadWriteSavedEndpoints
from musify.models.api.types import _ApiURISchema, _ApiURLSchema
from musify.models.cursors import PageCursor, HasPageCursor
from musify.models.exception import RequestError
from musify.spotify import API_URL
from musify.spotify.api._base import SpotifyEndpoints
from musify.spotify.api._types import SpotifyApiURL, SpotifyApiURISequence
from musify.spotify.collection.playlist import SpotifyPlaylist, SpotifyMutablePlaylist, SpotifyPlaylistTrack
from musify.spotify.item.track import SpotifyTrack
from musify.spotify.properties.uri import SpotifyResourceURI
from musify.spotify.user import SpotifyUser


@final
class _SpotifySavedPlaylistEndpoints(
    SpotifyEndpoints[SpotifyResourceURI, SpotifyPlaylist],
    PlaylistReadWriteSavedEndpoints[SpotifyResourceURI, SpotifyPlaylist, SpotifyUser],
):
    __final__ = True

    _saved_read_url: ClassVar[URL] = API_URL.joinpath("me/playlists")
    _saved_limit: ClassVar[int] = 50
    _saved_path: ClassVar[str] = "items"

    @staticmethod
    @validate_call
    def _format_playlist_body(
            name: str = None, public: bool = None, collaborative: bool = None, description: str = None
    ) -> JSON:
        if public and collaborative:
            raise RequestError("A playlist cannot be both public and collaborative.")

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
    @_ApiURLSchema.validate_call
    async def follow(self, url: SpotifyApiURL[SpotifyPlaylist], **kwargs) -> None:
        return await super().follow(url.joinpath("followers"))

    # WORKAROUND: Replace decorator with validate_call when this issue is resolved:
    # https://github.com/pydantic/pydantic/issues/7796
    @_ApiURLSchema.validate_call
    async def modify(self, url: SpotifyApiURL[SpotifyPlaylist], **kwargs) -> None:
        body = self._format_playlist_body(**kwargs)
        return await super().modify(**body)

    # WORKAROUND: Replace decorator with validate_call when this issue is resolved:
    # https://github.com/pydantic/pydantic/issues/7796
    @_ApiURLSchema.validate_call
    async def delete(self, url: SpotifyApiURL[SpotifyPlaylist], **kwargs) -> None:
        return await super().delete(url.joinpath("followers"))


@final
class SpotifyPlaylistEndpoints(
    SpotifyEndpoints[SpotifyResourceURI, SpotifyPlaylist],
    HasSavedEndpoints[_SpotifySavedPlaylistEndpoints],
    PlaylistReadWriteEndpoints[SpotifyResourceURI, SpotifyPlaylist, SpotifyPlaylistTrack],
):
    __final__ = True

    _batch_limit: ClassVar[int] = 100
    _extend_path: ClassVar[AliasChoices] = AliasChoices(
        "items",
        AliasPath("items", "items")
    )

    @validate_call
    async def get_all(
            self, collection: PageCursor | HasPageCursor | SpotifyPlaylist, show_bar: bool = True
    ) -> list[SpotifyPlaylistTrack]:
        try:
            return await super().get_all(collection, show_bar=show_bar)
        except ResponseError as exc:
            # WORKAROUND: Spotify returns 403 for private playlists, even if the the user is a collaborator
            #  and has access to the playlist.
            #  Just log a warning and return an empty list in this case, rather than raising an exception.
            if exc.response.status == 403:
                self.logger.warning(
                    f"Could not retrieve tracks for playlist {collection.name!r} due to insufficient permissions."
                )
                return []

            raise

    # WORKAROUND: Replace decorator with validate_call when this issue is resolved:
    # https://github.com/pydantic/pydantic/issues/7796
    @_ApiURLSchema.validate_call
    @_ApiURISchema.validate_call
    async def add(
            self,
            url: SpotifyApiURL[SpotifyMutablePlaylist],
            uris: SpotifyApiURISequence[LocalTrack | SpotifyTrack],
            limit: PositiveInt = None,
            show_bar: bool = True,
    ) -> int:
        return await super().add(url.joinpath("items"), uris=uris, limit=limit, show_bar=show_bar)

    # WORKAROUND: Replace decorator with validate_call when this issue is resolved:
    # https://github.com/pydantic/pydantic/issues/7796
    @_ApiURLSchema.validate_call
    @_ApiURISchema.validate_call
    async def remove(
            self,
            url: SpotifyApiURL[SpotifyMutablePlaylist],
            uris: SpotifyApiURISequence[LocalTrack | SpotifyTrack],
            limit: PositiveInt = None,
            show_bar: bool = True,
    ) -> int:
        return await super().remove(url.joinpath("items"), uris=uris, limit=limit, show_bar=show_bar)

    @staticmethod
    def _generate_remove_batch_body(values: Iterable[str]) -> JSON:
        return {"items": [{"uri": str(uri)} for uri in values]}
