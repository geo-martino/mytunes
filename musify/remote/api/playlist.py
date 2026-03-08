from aiorequestful.auth import Authoriser

from musify.models.properties.uri import URI
from musify.remote import RemoteModel
from musify.remote.api._base import RemoteEndpoints
from musify.remote.collection.playlist import RemotePlaylist


class PlaylistEndpoints[AT: Authoriser, UT: URI, RT: RemotePlaylist](RemoteEndpoints[AT, UT, RT]):
    async def extend_tracks(self, playlist: RT) -> None:
        """Extend the tracks in this album collection."""
        items = await self._extend_items_from_cursor(
            items=[], cursor=playlist.cursor, path=self._extend_path, kind="track"
        )
        # noinspection PyProtectedMember
        playlist._extend_items(items)


class PlaylistSavedEndpoints[AT: Authoriser, UT: URI, RT: RemotePlaylist](RemoteEndpoints[AT, UT, RT]):
    pass


class HasPlaylistEndpoints[ET: PlaylistEndpoints](RemoteModel):
    playlists: ET
