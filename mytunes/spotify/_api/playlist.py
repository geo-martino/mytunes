import base64
from collections.abc import Iterable
from typing import ClassVar, final

from aiohttp import ClientResponse
from aiorequestful.response.exception import ResponseError
from pydantic import validate_call, PositiveInt, AliasPath, AliasChoices
from pydantic.json_schema import JsonSchemaValue
from yarl import URL

from mytunes.core.properties.image import ImageSource, PILImageFileT
from mytunes.core.properties.uri import HasURI
from mytunes.exception import RequestError
from mytunes.spotify import API_URL
from mytunes.spotify._api._base import SpotifyEndpoints, _SpotifyLibraryEndpoints
from mytunes.spotify._api._types import SpotifyApiURL, SpotifyApiURISequence, SpotifyApiURI
from mytunes.spotify.user import SpotifyUser
from .._collection.playlist import SpotifyPlaylist, SpotifyMutablePlaylist
from .._item.track import SpotifyTrack, SpotifyPlaylistTrack
from .._properties.uri import SpotifyResourceURI
from ... import PROGRAM_NAME
from ...core.api import HasLibraryEndpoints
from ...core.api.playlist import PlaylistLibraryEndpoints, PlaylistReadWriteEndpoints
from ...core.api.types import ApiURISchema, ApiURLSchema
from ...core.cursors import PageCursor, HasPageCursor


@final
class _SpotifyPlaylistLibraryEndpoints(
    PlaylistLibraryEndpoints[SpotifyResourceURI, SpotifyPlaylist, SpotifyUser],
    _SpotifyLibraryEndpoints[SpotifyResourceURI, SpotifyPlaylist],
):
    __final__ = True

    _create_url: ClassVar[URL] = API_URL.joinpath("me/playlists")

    _extend_path: ClassVar[AliasChoices] = AliasChoices(
        "items",
        AliasPath("items", "items")
    )

    _read_all_url: ClassVar[URL] = API_URL.joinpath("me/playlists")
    _read_all_limit: ClassVar[int] = 50
    _read_all_path: ClassVar[str] = "items"

    _write_url: ClassVar[URL] = API_URL.joinpath("me/library")
    _write_limit: ClassVar[int] = 40

    @ApiURISchema.validate_call()  # WORKAROUND: replace with @validate_call when supported
    async def add(self, uri: SpotifyApiURI[SpotifyPlaylist], **kwargs) -> None:
        url = self._write_url.with_query(dict(uris=uri))
        return await super().add(url)

    @ApiURISchema.validate_call()  # WORKAROUND: replace with @validate_call when supported
    async def remove(self, uri: SpotifyApiURI[SpotifyPlaylist], **kwargs) -> None:
        url = self._write_url.with_query(dict(uris=uri))
        return await super().remove(url)

    @ApiURLSchema.validate_call()  # WORKAROUND: replace with @validate_call when supported
    async def modify(
            self,
            url: SpotifyApiURL[SpotifyPlaylist],
            image: bytes | ImageSource | PILImageFileT | None = None,
            **kwargs
    ) -> None:
        if not kwargs and not image:
            self._handler.log("SKIP", url, message="No playlist data given to modify")

        if kwargs:
            await super().modify(url, **kwargs)
        if image is not None:
            await self._modify_image(url, image=image)

    async def _modify_image(
            self, url: SpotifyApiURL[SpotifyPlaylist], image: bytes | ImageSource | PILImageFileT
    ) -> None:
        data, mime = await self._get_image_data(image)
        if len(data) > 256 * 10e3:
            self._logger.warning(f"Cannot modify image, image too large: {len(data)} > 256 KB | {url}")
            return

        if not url.path.endswith("/images"):
            url = url.joinpath("images")

        encoded_data = base64.b64encode(data).decode("ascii")
        await self._handler.put(url, data=encoded_data, headers={"Content-Type": mime})

    @classmethod
    @validate_call
    async def _format_playlist_body(
            cls, name: str | None = None, public: bool = None, collaborative: bool = None, description: str = None
    ) -> JsonSchemaValue:
        if public and collaborative:
            raise RequestError("A playlist cannot be both public and collaborative.")

        body: JsonSchemaValue = {"name": name or f"{PROGRAM_NAME} Playlist"}

        if public is not None:
            body["public"] = public
        if collaborative is not None:
            body["collaborative"] = collaborative
        if description is not None:
            body["description"] = description

        return body


@final
class SpotifyPlaylistEndpoints(
    SpotifyEndpoints[SpotifyResourceURI, SpotifyPlaylist],
    HasLibraryEndpoints[_SpotifyPlaylistLibraryEndpoints],
    PlaylistReadWriteEndpoints[SpotifyResourceURI, SpotifyPlaylist, SpotifyPlaylistTrack],
):
    __final__ = True

    _write_limit: ClassVar[int] = 100
    _extend_path: ClassVar[AliasChoices] = AliasChoices(
        "items",
        AliasPath("items", "items")
    )

    _create_url: ClassVar[URL] = API_URL.joinpath("me/playlists")

    @validate_call
    async def get_all_items(self, collection: PageCursor | HasPageCursor | SpotifyPlaylist) -> list[SpotifyPlaylistTrack]:
        try:

            return await super().get_all_items(collection)
        except ResponseError as exc:
            # WORKAROUND: Spotify returns 403 for private playlists, even if the user is a collaborator
            #  and has access to the playlist.
            #  Just log a warning and return an empty list in this case, rather than raising an exception.
            if isinstance(exc.response, ClientResponse) and exc.response.status == 403:
                self._logger.warning(
                    f"Could not retrieve tracks for playlist {collection.name!r} due to insufficient permissions."
                )
                return []

            raise

    @ApiURLSchema.validate_call()  # WORKAROUND: replace with @validate_call when supported
    @ApiURISchema.validate_call("uris", is_sequence=True)
    async def add(
            self,
            url: SpotifyApiURL[SpotifyMutablePlaylist],
            uris: SpotifyApiURISequence[HasURI | SpotifyTrack],
            limit: PositiveInt = None,
    ) -> int:
        return await super().add(url.joinpath("items"), uris=uris, limit=limit)

    @staticmethod
    def _generate_add_collection_kwargs(values: Iterable[str]) -> dict[str, JsonSchemaValue]:
        return {"json": {"uris": list(map(str, values))}}

    @ApiURLSchema.validate_call()  # WORKAROUND: replace with @validate_call when supported
    @ApiURISchema.validate_call("uris", is_sequence=True)
    async def remove(
            self,
            url: SpotifyApiURL[SpotifyMutablePlaylist],
            uris: SpotifyApiURISequence[HasURI | SpotifyTrack],
            limit: PositiveInt = None,
    ) -> int:
        return await super().remove(url.joinpath("items"), uris=uris, limit=limit)

    @staticmethod
    def _generate_remove_collection_kwargs(values: Iterable[str]) -> dict[str, JsonSchemaValue]:
        return {"json": {"items": [{"uri": str(uri)} for uri in values]}}
