from aiorequestful.auth import Authoriser

from musify.models.properties.uri import URI
from musify.remote import RemoteModel
from musify.remote.api._base import RemoteEndpoints
from musify.remote.collection.genre import RemoteGenreCollection
from musify.remote.item.genre import RemoteGenre


class GenreEndpoints[AT: Authoriser, UT: URI, RT: RemoteGenre](RemoteEndpoints[AT, UT, RT]):
    pass


class GenreSavedEndpoints[AT: Authoriser, UT: URI, RT: RemoteGenre](RemoteEndpoints[AT, UT, RT]):
    pass


class GenreCollectionEndpoints[AT: Authoriser, UT: URI, RT: RemoteGenreCollection](GenreEndpoints[AT, UT, RT]):
    async def extend_tracks(self, genre: RT) -> None:
        """Extend the tracks in this genre collection."""
        await self._extend_items_from_cursor(
            items=genre.tracks, cursor=genre.cursor, path=self._extend_path, kind="genre"
        )


class HasGenreEndpoints[ET: GenreEndpoints](RemoteModel):
    genres: ET
