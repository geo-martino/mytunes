from collections.abc import Sequence
from typing import Annotated, ClassVar, Type

from pydantic import validate_call, Field, PositiveInt
from yarl import URL

from musify.models.properties.uri import URI
from musify.remote.api._endpoints import RemoteEndpoints, RemoteGetSingleEndpoints, RemoteGetManyEndpoints, \
    RemoteGetSavedEndpoints, RemoteMutableCollectionEndpoints, HasEndpoints
from musify.remote.api.types import ApiURLSchema
from musify.remote.collection.playlist import RemotePlaylist, RemoteMutablePlaylist
from musify.remote.user import RemoteUser


class PlaylistEndpoints[UT: URI, RT: RemotePlaylist](RemoteEndpoints[UT, RT]):
    type: ClassVar[Type] = RemotePlaylist


class PlaylistGetSingleEndpoints[UT: URI, RT: RemotePlaylist](
    PlaylistEndpoints[UT, RT], RemoteGetSingleEndpoints[UT, RT]
):
    pass


class PlaylistGetManyEndpoints[UT: URI, RT: RemotePlaylist](
    PlaylistEndpoints[UT, RT], RemoteGetManyEndpoints[UT, RT]
):
    pass


class PlaylistMutableEndpoints[UT: URI, RT: RemoteMutablePlaylist](
    PlaylistGetSingleEndpoints[UT, RT], RemoteMutableCollectionEndpoints[UT, RT],
):
    type: ClassVar[Type] = RemoteMutablePlaylist
    _extend_type: ClassVar[str] = "track"


class PlaylistGetSavedEndpoints[UT: URI, RT: RemotePlaylist, OT: RemoteUser](
    PlaylistEndpoints[UT, RT], RemoteGetSavedEndpoints[UT, RT]
):
    @validate_call
    async def get_by_user(self, user: OT, limit: PositiveInt | None = None) -> list[RT]:
        """Get the current user's saved playlists owned by the given user."""
        playlists = await self.get_all(limit=limit)
        return [playlist for playlist in playlists if playlist.owner == user]

    @validate_call
    async def get_by_name(self, name: str, limit: PositiveInt | None = None) -> RT | None:
        """Get the user's saved playlist with the given name. Returns ``None`` if no such playlist exists."""
        playlists = await self.get_all(limit=limit)
        return next((playlist for playlist in playlists if playlist.name == name), None)

    @validate_call
    async def get_by_names(self, names: Sequence[str], limit: PositiveInt | None = None) -> list[RT]:
        """Get the user's saved playlists with the given names."""
        playlists = await self.get_all(limit=limit)
        playlists_mapped = {playlist.name: playlist for playlist in playlists}
        return [playlists_mapped[name] for name in names if name in playlists_mapped]


class PlaylistMutableSavedEndpoints[UT: URI, RT: RemoteMutablePlaylist, OT: RemoteUser](
    PlaylistGetSavedEndpoints[UT, RT, OT],
):
    type: ClassVar[Type] = RemoteMutablePlaylist

    @validate_call
    async def create(self, **kwargs) -> RT:
        """Create a playlist in the current user's library."""
        response = await self._handler.post(self._saved_url, json=kwargs)
        return self.__class__.create_model(response)

    # WORKAROUND: Replace decorator with validate_call when this issue is resolved:
    # https://github.com/pydantic/pydantic/issues/7796
    @ApiURLSchema.validate_call
    async def follow(self, url: Annotated[URL, ApiURLSchema[UT, RT]], **kwargs) -> None:
        """Add an existing playlist to the current user's library."""
        await self._handler.put(url)

    # WORKAROUND: Replace decorator with validate_call when this issue is resolved:
    # https://github.com/pydantic/pydantic/issues/7796
    @ApiURLSchema.validate_call
    async def modify(self, url: Annotated[URL, ApiURLSchema[UT, RT]], **kwargs) -> None:
        """Modify details about a playlist in the current user's library."""
        await self._handler.put(url, json=kwargs)

    # WORKAROUND: Replace decorator with validate_call when this issue is resolved:
    # https://github.com/pydantic/pydantic/issues/7796
    @ApiURLSchema.validate_call
    async def delete(self, url: Annotated[URL, ApiURLSchema[UT, RT]]) -> None:
        """Delete the playlist from the current user's library."""
        await self._handler.delete(url)

    @validate_call
    async def get_or_create(self, name: str, **kwargs) -> RT:
        """Get the playlist if it exists in the current user's library or create a new one."""
        # noinspection PyArgumentList
        playlist = await self.get_by_name(name=name)
        if playlist is None:
            playlist = await self.create(name=name, **kwargs)
        return playlist


class HasPlaylistEndpoints[ET: PlaylistEndpoints](HasEndpoints):
    playlists: ET = Field(
        description="Access playlist endpoints for the API."
    )
