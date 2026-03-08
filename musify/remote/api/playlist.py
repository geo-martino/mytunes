from typing import Annotated

from aiorequestful.auth import Authoriser
from pydantic import validate_call
from yarl import URL

from musify.models.properties.uri import URI
from musify.remote import RemoteModel
from musify.remote.api._base import RemoteEndpoints, RemoteGetSingleEndpoints, RemoteGetManyEndpoints, \
    RemoteGetSavedEndpoints, RemoteMutableCollectionEndpoints
from musify.remote.api._types import ApiURLSchema
from musify.remote.collection.playlist import RemotePlaylist, RemoteMutablePlaylist


class PlaylistEndpoints[AT: Authoriser, UT: URI, RT: RemotePlaylist](RemoteEndpoints[AT, UT, RT]):
    pass


class PlaylistGetSingleEndpoints[AT: Authoriser, UT: URI, RT: RemotePlaylist](
    PlaylistEndpoints[AT, UT, RT], RemoteGetSingleEndpoints[AT, UT, RT]
):
    async def extend_tracks(self, playlist: RT) -> None:
        """Extend the tracks in this album collection."""
        items = await self._extend_items_from_cursor(
            items=[], cursor=playlist.cursor, path=self._extend_path, kind="track"
        )
        # noinspection PyProtectedMember
        playlist._extend_items(items)


class PlaylistGetManyEndpoints[AT: Authoriser, UT: URI, RT: RemotePlaylist](
    PlaylistEndpoints[AT, UT, RT], RemoteGetManyEndpoints[AT, UT, RT]
):
    pass


class PlaylistGetSavedEndpoints[AT: Authoriser, UT: URI, RT: RemotePlaylist](
    PlaylistEndpoints[AT, UT, RT], RemoteGetSavedEndpoints[AT, UT, RT]
):
    pass


class PlaylistMutableEndpoints[AT: Authoriser, UT: URI, RT: RemotePlaylist](
    PlaylistGetSavedEndpoints[AT, UT, RT],
    RemoteMutableCollectionEndpoints[AT, UT, RT],
    RemoteMutablePlaylist[AT, UT, RT],
):
    @validate_call
    async def create(self, **kwargs) -> None:
        """Create a playlist in the current user's library."""
        await self.handler.post(self._saved_url, json=kwargs)

    @ApiURLSchema.validate_call
    async def delete(self, playlist: Annotated[URL, ApiURLSchema[UT, RT]]) -> None:
        """Delete the playlist from the current user's library."""
        await self.handler.delete(playlist)


class HasPlaylistEndpoints[ET: PlaylistEndpoints](RemoteModel):
    playlists: ET
