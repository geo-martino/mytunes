from typing import ClassVar, final, Literal, Type, Any, get_args

from pydantic import AliasPath, validate_call
from pydantic.json_schema import JsonSchemaValue
from yarl import URL

from musify.models.api import HasSavedEndpoints
from musify.models.api.artist import ArtistReadItemEndpoints, ArtistReadItemsEndpoints, \
    ArtistReadSavedEndpoints, ArtistReadCollectionEndpoints, ArtistWriteSavedEndpoints, ArtistEndpoints
from musify.models.api.types import ApiURL, _ApiURLSchema
from musify.models.cursors import PageCursor
from musify.spotify import API_URL
from musify.spotify.api._base import SpotifyEndpoints
from musify.spotify.collection.artist import SpotifyArtistCollection
from musify.spotify.cursors import SpotifyInitialCursor, SpotifyIndexCursor
from musify.spotify.item.album import SpotifyAlbum
from musify.spotify.item.artist import SpotifyArtist
from musify.spotify.properties.uri import SpotifyResourceURI

_ALBUM_TYPE = Literal["album", "single", "compilation", "appears_on"]
_ALL_ALBUM_TYPES = get_args(_ALBUM_TYPE)


class _SpotifyArtistEndpoints(
    ArtistEndpoints[SpotifyResourceURI, SpotifyArtist],
    SpotifyEndpoints[SpotifyResourceURI, SpotifyArtist],
):
    type: ClassVar[Type] = SpotifyArtistCollection  # override to force creation of collections from responses

    @staticmethod
    def _add_albums_cursor_to_item[T: dict[str, Any]](item: T) -> T:
        url = URL(item["href"]).joinpath("albums")
        item["albums"] = SpotifyInitialCursor(url=url).model_dump(mode="json")
        return item

    @classmethod
    def _get_items_from_response(cls, response: JsonSchemaValue, path: str | AliasPath) -> list[JsonSchemaValue]:
        return list(map(cls._add_albums_cursor_to_item, super()._get_items_from_response(response, path=path)))


@final
class _SpotifySavedArtistEndpoints(
    _SpotifyArtistEndpoints,
    ArtistReadSavedEndpoints[SpotifyResourceURI, SpotifyArtist],
    ArtistWriteSavedEndpoints[SpotifyResourceURI, SpotifyArtist],
):
    __final__ = True

    _read_url: ClassVar[URL] = API_URL.joinpath("me/following").with_query(type="artist")
    _read_limit: ClassVar[int] = 50
    _read_path: ClassVar[AliasPath] = AliasPath("artists", "items")

    _write_url: ClassVar[URL] = API_URL.joinpath("me/library")
    _write_limit: ClassVar[int] = 40


@final
class SpotifyArtistEndpoints(
    _SpotifyArtistEndpoints,
    HasSavedEndpoints[_SpotifySavedArtistEndpoints],
    ArtistReadItemEndpoints[SpotifyResourceURI, SpotifyArtist],
    ArtistReadItemsEndpoints[SpotifyResourceURI, SpotifyArtist],
    ArtistReadCollectionEndpoints[SpotifyResourceURI, SpotifyArtistCollection, SpotifyAlbum],
):
    __final__ = True

    _many_url: ClassVar[URL] = API_URL.joinpath("artists")
    _many_limit: ClassVar[int] = 50
    _many_path: ClassVar[str] = "artists"

    _extend_path: ClassVar[str] = "items"

    @_ApiURLSchema.validate_call()  # WORKAROUND: replace with @validate_call when supported
    async def get(self, url: ApiURL[SpotifyResourceURI, SpotifyArtist]) -> SpotifyArtistCollection:
        response = await self._handler.get(url)
        self._add_albums_cursor_to_item(response)
        return self.__class__.create_model(response, context=self._model_context, kind=SpotifyArtistCollection)

    @validate_call
    async def get_all(
            self,
            collection: SpotifyArtistCollection | PageCursor,
            types: set[_ALBUM_TYPE] = _ALL_ALBUM_TYPES,
            show_bar: bool = True,
    ) -> list[SpotifyAlbum]:
        match collection:
            case PageCursor() as cursor:
                pass
            case SpotifyArtistCollection() as artist:
                cursor = artist.cursor

        query = {"include_groups": ",".join(map(str, types))}
        cursor.url = cursor.url.update_query(query)
        return await super().get_all(cursor, show_bar=show_bar)
