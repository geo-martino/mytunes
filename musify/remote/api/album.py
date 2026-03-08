from aiorequestful.auth import Authoriser

from musify.models.properties.uri import URI
from musify.remote import RemoteModel
from musify.remote.api._base import RemoteEndpoints
from musify.remote.collection.album import RemoteAlbumCollection
from musify.remote.item.album import RemoteAlbum


class AlbumEndpoints[AT: Authoriser, UT: URI, RT: RemoteAlbum](RemoteEndpoints[AT, UT, RT]):
    pass


class AlbumSavedEndpoints[AT: Authoriser, UT: URI, RT: RemoteAlbum](RemoteEndpoints[AT, UT, RT]):
    pass


class AlbumCollectionEndpoints[AT: Authoriser, UT: URI, RT: RemoteAlbumCollection](AlbumEndpoints[AT, UT, RT]):
    async def extend_tracks(self, album: RT) -> None:
        """Extend the tracks in this album collection."""
        await self._extend_items_from_cursor(
            items=album.tracks, cursor=album.cursor, path=self._extend_path, kind="track"
        )


class HasAlbumEndpoints[ET: AlbumEndpoints](RemoteModel):
    albums: ET
