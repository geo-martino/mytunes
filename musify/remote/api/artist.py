from aiorequestful.auth import Authoriser

from musify.models.properties.uri import URI
from musify.remote import RemoteModel
from musify.remote.api._base import RemoteEndpoints
from musify.remote.collection.artist import RemoteArtistCollection
from musify.remote.item.artist import RemoteArtist


class ArtistEndpoints[AT: Authoriser, UT: URI, RT: RemoteArtist](RemoteEndpoints[AT, UT, RT]):
    pass


class ArtistSavedEndpoints[AT: Authoriser, UT: URI, RT: RemoteArtist](RemoteEndpoints[AT, UT, RT]):
    pass


class ArtistCollectionEndpoints[AT: Authoriser, UT: URI, RT: RemoteArtistCollection](ArtistEndpoints[AT, UT, RT]):
    async def extend_albums(self, artist: RT) -> None:
        """Extend the albums in this artist collection."""
        items = await self._extend_items_from_cursor(
            items=[], cursor=artist.cursor, path=self._extend_path, kind="album"
        )
        # noinspection PyProtectedMember
        artist._extend_items(items)


class HasArtistEndpoints[ET: ArtistEndpoints](RemoteModel):
    artists: ET
