from collections.abc import Sequence
from typing import ClassVar, overload

from pydantic import validate_call, Field, PositiveInt, PrivateAttr
from pydantic.json_schema import JsonSchemaValue
from yarl import URL

from mytunes.core.api import HasLibraryEndpoints
from mytunes.core.api._endpoints import Endpoints, ItemReadEndpoints, BatchReadEndpoints, \
    BatchReadAllEndpoints, CollectionWriteEndpoints, HasEndpoints, CollectionReadEndpoints, \
    BatchWriteEndpoints, _URL_TYPE, _URI_TYPE
from mytunes.core.api.types import ApiURL, ApiURLSchema, ApiURISchema, ApiURISequence
from mytunes.properties.uri import URI
from .._collection.playlist import RemotePlaylist
from .._item.track import RemoteTrack
from .._item.user import RemoteUser


class PlaylistEndpoints[UT: URI, RT: RemotePlaylist](Endpoints[UT, RT]):
    pass


class PlaylistReadEndpoints[UT: URI, RT: RemotePlaylist, IT: RemoteTrack](
    PlaylistEndpoints[UT, RT],
    ItemReadEndpoints[UT, RT],
    CollectionReadEndpoints[UT, RT, IT],
):
    pass


class PlaylistWriteEndpoints[UT: URI, RT: RemotePlaylist, IT: RemoteTrack](
    PlaylistEndpoints[UT, RT],
    CollectionWriteEndpoints[UT, RT, IT],
):
    pass


class PlaylistReadWriteEndpoints[UT: URI, RT: RemotePlaylist, IT: RemoteTrack](
    PlaylistReadEndpoints[UT, RT, IT],
    PlaylistWriteEndpoints[UT, RT, IT],
):
    @overload
    async def add_and_skip_duplicates(
            self, url: _URL_TYPE[UT, RT], uris: Sequence[_URI_TYPE[RT]], limit: PositiveInt | None = None,
    ) -> int: ...

    @overload
    async def add_and_skip_duplicates(
            self, url: URL, uris: Sequence[UT], limit: PositiveInt | None = None,
    ) -> int: ...

    @ApiURLSchema.validate_call()  # WORKAROUND: replace with @validate_call when supported
    @ApiURISchema.validate_call("uris", is_sequence=True)
    async def add_and_skip_duplicates(
            self, url: ApiURL[UT, RT], uris: ApiURISequence[UT, IT], limit: PositiveInt = None,
    ) -> int:
        """Add items to the playlist and avoid adding any duplicates."""
        collection = await self.get(url)
        items = await self.get_all(collection)

        uris_unique = []
        uris_current = {item.uri for item in items}
        for uri in uris:
            if uri not in uris_unique and uri not in uris_current:
                uris_unique.append(uri)

        return await self.add(url, uris_unique, limit=limit)


class PlaylistBatchReadEndpoints[UT: URI, RT: RemotePlaylist](
    PlaylistEndpoints[UT, RT], BatchReadEndpoints[UT, RT]
):
    pass


class PlaylistBatchReadAllEndpoints[UT: URI, RT: RemotePlaylist, OT: RemoteUser](
    PlaylistEndpoints[UT, RT], BatchReadAllEndpoints[UT, RT]
):
    @validate_call
    async def get_by_user(self, user: OT, limit: PositiveInt | None = None) -> list[RT]:
        """Get the current user's library playlists owned by the given user."""
        playlists = await self.get_all(limit=limit)
        return [playlist for playlist in playlists if playlist.owner == user]

    @validate_call
    async def get_by_name(self, name: str, limit: PositiveInt | None = None) -> RT | None:
        """Get the user's library playlist with the given name. Returns ``None`` if no such playlist exists."""
        playlists = await self.get_all(limit=limit)
        return next((playlist for playlist in playlists if playlist.name == name), None)

    @validate_call
    async def get_by_names(self, names: Sequence[str], limit: PositiveInt | None = None) -> list[RT]:
        """Get the user's library playlists with the given names."""
        playlists = await self.get_all(limit=limit)
        playlists_mapped = {playlist.name: playlist for playlist in playlists}
        return [playlists_mapped[name] for name in names if name in playlists_mapped]


class PlaylistBatchWriteEndpoints[UT: URI, RT: RemotePlaylist](
    PlaylistEndpoints[UT, RT], BatchWriteEndpoints[UT, RT]
):
    pass


# noinspection PyAbstractClass
class PlaylistLibraryEndpoints[UT: URI, RT: RemotePlaylist, OT: RemoteUser](
    PlaylistBatchReadAllEndpoints[UT, RT, OT],
    PlaylistBatchWriteEndpoints[UT, RT],
):
    _create_url: ClassVar[URL] = PrivateAttr(
        # description="The API endpoint to create a playlist for the current user.",
    )

    @validate_call
    async def create(self, **kwargs) -> RT | None:
        """Create a playlist in the current user's library."""
        if not kwargs:
            self._handler.log("SKIP", self._create_url, message="No playlist data given to create")
            return None

        body = await self._format_playlist_body(**kwargs)
        response = await self._handler.post(self._create_url, json=body)
        playlist = type(self).create_model(response, context=self._model_context)

        message = f"Created playlist: {playlist.name!r} -> {playlist.uri.api_url}"
        self._handler.log("DONE", self._create_url, message=message)
        return playlist

    @overload
    async def add(self, url: _URL_TYPE[UT, RT]) -> None: ...

    @overload
    async def add(self, url: URL) -> None: ...

    @ApiURLSchema.validate_call()  # WORKAROUND: replace with @validate_call when supported
    async def add(self, url: ApiURL[UT, RT]) -> None:
        """Add an existing playlist to the current user's library."""
        await self._handler.put(url)

    @overload
    async def remove(self, url: _URL_TYPE[UT, RT]) -> None: ...

    @overload
    async def remove(self, url: URL) -> None: ...

    @ApiURLSchema.validate_call()  # WORKAROUND: replace with @validate_call when supported
    async def remove(self, url: ApiURL[UT, RT]) -> None:
        """Delete the playlist from the current user's library."""
        await self._handler.delete(url)

    @overload
    async def modify(self, url: _URL_TYPE[UT, RT], **kwargs) -> None: ...

    @overload
    async def modify(self, url: URL, **kwargs) -> None: ...

    @ApiURLSchema.validate_call()  # WORKAROUND: replace with @validate_call when supported
    async def modify(self, url: ApiURL[UT, RT], **kwargs) -> None:
        """Modify details about a playlist in the current user's library."""
        if not kwargs:
            self._handler.log("SKIP", url, message="No playlist data given to modify")
            return

        body = await self._format_playlist_body(**kwargs)
        await self._handler.put(url, json=body)

    @classmethod
    async def _format_playlist_body(cls, **kwargs) -> JsonSchemaValue:
        """Format the playlist body for playlist endpoints."""
        return kwargs

    @validate_call
    async def get_or_create(self, name: str, **kwargs) -> RT:
        """Get the playlist if it exists in the current user's library or create a new one."""
        # noinspection PyArgumentList
        playlist = await self.get_by_name(name=name)
        if playlist is None:
            playlist = await self.create(name=name, **kwargs)
        return playlist


class HasPlaylistEndpoints[ET: PlaylistEndpoints | HasLibraryEndpoints](HasEndpoints):
    playlists: ET = Field(
        description="Access playlist endpoints for the API."
    )
