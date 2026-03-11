from typing import ClassVar, final, Literal

from pydantic import AliasPath, validate_call
from yarl import URL

from musify.models.api import HasSavedEndpoints
from musify.models.api.artist import ArtistReadItemEndpoints, ArtistReadItemsEndpoints, \
    ArtistReadSavedEndpoints, ArtistReadCollectionEndpoints, ArtistWriteSavedEndpoints
from musify.models.collection import ItemsCursor
from musify.spotify import API_URL
from musify.spotify.api._base import SpotifyEndpoints
from musify.spotify.collection.artist import SpotifyArtistCollection
from musify.spotify.item.artist import SpotifyArtist
from musify.spotify.properties.uri import SpotifyResourceURI


@final
class _SpotifySavedArtistEndpoints(
    SpotifyEndpoints[SpotifyResourceURI, SpotifyArtist],
    ArtistReadSavedEndpoints[SpotifyResourceURI, SpotifyArtist],
    ArtistWriteSavedEndpoints[SpotifyResourceURI, SpotifyArtist],
):
    __final__ = True

    _saved_read_url: ClassVar[URL] = API_URL.joinpath("me/following").with_query(type="artist")
    _saved_write_url: ClassVar[URL] = API_URL.joinpath("me/following").with_query(type="artist")
    _saved_limit: ClassVar[int] = 50
    _saved_path: ClassVar[AliasPath] = AliasPath("artists", "items")

    _batch_limit: ClassVar[int] = 50


@final
class SpotifyArtistEndpoints(
    SpotifyEndpoints[SpotifyResourceURI, SpotifyArtist],
    HasSavedEndpoints[_SpotifySavedArtistEndpoints],
    ArtistReadItemEndpoints[SpotifyResourceURI, SpotifyArtist],
    ArtistReadItemsEndpoints[SpotifyResourceURI, SpotifyArtist],
    ArtistReadCollectionEndpoints[SpotifyResourceURI, SpotifyArtistCollection],
):
    __final__ = True

    _many_url: ClassVar[URL] = API_URL.joinpath("artists")
    _many_limit: ClassVar[int] = 50
    _many_path: ClassVar[str] = "artists"

    _extend_path: ClassVar[str] = "items"

    @validate_call
    async def get_all(
            self,
            collection: SpotifyArtistCollection | ItemsCursor,
            types: set[Literal["album", "single", "compilation", "appears_on"]] | None = None
    ) -> list[SpotifyArtist]:
        query = {"include_groups": ",".join(types)} if types else {}
        match collection:
            case ItemsCursor() as cursor:
                pass
            case SpotifyArtistCollection() as artist:
                cursor = artist.cursor

        if cursor.next is not None:
            cursor.next = cursor.next.update_query(query)
        else:
            cursor.current = cursor.current.update_query(query)

        return await super().get_all(collection)
