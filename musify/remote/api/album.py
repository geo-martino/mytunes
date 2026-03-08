from aiorequestful.auth import Authoriser

from musify.models.properties.uri import URI
from musify.remote import RemoteModel
from musify.remote.api._base import RemoteEndpoints, RemoteGetSingleEndpoints, RemoteGetManyEndpoints, \
    RemoteGetSavedEndpoints, RemoteCollectionEndpoints
from musify.remote.collection.album import RemoteAlbumCollection
from musify.remote.item.album import RemoteAlbum


class AlbumEndpoints[AT: Authoriser, UT: URI, RT: RemoteAlbum](RemoteEndpoints[AT, UT, RT]):
    pass


class AlbumGetSingleEndpoints[AT: Authoriser, UT: URI, RT: RemoteAlbum](
    AlbumEndpoints[AT, UT, RT], RemoteGetSingleEndpoints[AT, UT, RT]
):
    pass


class AlbumGetManyEndpoints[AT: Authoriser, UT: URI, RT: RemoteAlbum](
    AlbumEndpoints[AT, UT, RT], RemoteGetManyEndpoints[AT, UT, RT]
):
    pass


class AlbumGetSavedEndpoints[AT: Authoriser, UT: URI, RT: RemoteAlbum](
    AlbumEndpoints[AT, UT, RT], RemoteGetSavedEndpoints[AT, UT, RT]
):
    pass


class AlbumCollectionEndpoints[AT: Authoriser, UT: URI, RT: RemoteAlbumCollection](
    AlbumEndpoints[AT, UT, RT], RemoteCollectionEndpoints[AT, UT, RT]
):
    async def extend_tracks(self, album: RT) -> None:
        """Extend the tracks in this album collection."""
        items = await self._extend_items_from_cursor(
            items=[], cursor=album.cursor, path=self._extend_path, kind="track"
        )
        # noinspection PyProtectedMember
        album._extend_items(items)


class HasAlbumEndpoints[ET: AlbumEndpoints](RemoteModel):
    albums: ET
