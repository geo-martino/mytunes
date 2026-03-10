from typing import ClassVar, final, Literal

from pydantic import AliasPath, Field, validate_call
from yarl import URL

from musify.remote.api.artist import ArtistGetSingleEndpoints, ArtistGetManyEndpoints, \
    ArtistGetSavedEndpoints, ArtistCollectionEndpoints, ArtistMutableSavedEndpoints
from musify.remote.collection import ItemsCursor
from musify.spotify import API_URL
from musify.spotify.api._base import SpotifyEndpoints
from musify.spotify.collection.artist import SpotifyArtistCollection
from musify.spotify.item.artist import SpotifyArtist
from musify.spotify.properties.uri import SpotifyResourceURI


@final
class _SpotifySavedArtistEndpoints(
    SpotifyEndpoints[SpotifyResourceURI, SpotifyArtist],
    ArtistGetSavedEndpoints[SpotifyResourceURI, SpotifyArtist],
    ArtistMutableSavedEndpoints[SpotifyResourceURI, SpotifyArtist],
):
    __final__ = True

    _saved_url: ClassVar[URL] = API_URL.joinpath("me/following").with_query(type="artist")
    _saved_limit: ClassVar[int] = 50
    _saved_path: ClassVar[AliasPath] = AliasPath("artists", "items")

    _batch_limit: ClassVar[int] = 50


@final
class SpotifyArtistEndpoints(
    SpotifyEndpoints[SpotifyResourceURI, SpotifyArtist],
    ArtistGetSingleEndpoints[SpotifyResourceURI, SpotifyArtist],
    ArtistGetManyEndpoints[SpotifyResourceURI, SpotifyArtist],
    ArtistCollectionEndpoints[SpotifyResourceURI, SpotifyArtistCollection],
):
    __final__ = True

    _many_url: ClassVar[URL] = API_URL.joinpath("artists")
    _many_limit: ClassVar[int] = 50
    _many_path: ClassVar[str] = "artists"

    _extend_path: ClassVar[str] = "items"

    following: _SpotifySavedArtistEndpoints = Field(
        description="Access endpoints for the current user's followed artist.",
    )

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
