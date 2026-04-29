from typing import ClassVar, final, Literal, Any, get_args

from pydantic import AliasPath, validate_call, OnErrorOmit
from pydantic.json_schema import JsonSchemaValue
from yarl import URL

from mytunes.spotify import API_URL
from mytunes.spotify._api._base import SpotifyEndpoints, _SpotifyLibraryEndpoints
from mytunes.spotify.cursors import SpotifyInitialCursor
from .._collection.artist import SpotifyArtistCollection
from .._item.album import SpotifyAlbum
from .._item.artist import SpotifyArtist
from .._properties.uri import SpotifyResourceURI
from ...core.api import HasLibraryEndpoints, ItemReadAllEndpoints, BatchWriteEndpoints, ItemReadEndpoints, \
    BatchReadEndpoints, CollectionReadEndpoints
from ...core.api.types import ApiURL, ApiURLSchema
from ...core.cursors import PageCursor

_ALBUM_TYPE = Literal["album", "single", "compilation", "appears_on"]
_ALL_ALBUM_TYPES = get_args(_ALBUM_TYPE)


class _SpotifyArtistEndpoints(
    SpotifyEndpoints[SpotifyResourceURI, SpotifyArtistCollection],
):
    @staticmethod
    def _add_albums_cursor_to_item[T: dict[str, Any]](item: T) -> T:
        url = URL(item["href"]).joinpath("albums")
        item["albums"] = SpotifyInitialCursor(url=url).model_dump(mode="json")
        return item

    @classmethod
    def _get_items_from_response(cls, response: JsonSchemaValue, path: str | AliasPath) -> list[JsonSchemaValue]:
        return list(map(cls._add_albums_cursor_to_item, super()._get_items_from_response(response, path=path)))


@final
class _SpotifyArtistLibraryEndpoints(
    _SpotifyArtistEndpoints,
    _SpotifyLibraryEndpoints[SpotifyResourceURI, SpotifyArtistCollection],
    ItemReadAllEndpoints[SpotifyResourceURI, SpotifyArtistCollection],
    BatchWriteEndpoints[SpotifyResourceURI, SpotifyArtistCollection],
):
    __final__ = True

    _read_all_url: ClassVar[URL] = API_URL.joinpath("me/following").with_query(type="artist")
    _read_all_limit: ClassVar[int] = 50
    _read_all_path: ClassVar[AliasPath] = AliasPath("artists", "items")

    _write_url: ClassVar[URL] = API_URL.joinpath("me/library")
    _write_limit: ClassVar[int] = 40


@final
class SpotifyArtistEndpoints(
    _SpotifyArtistEndpoints,
    HasLibraryEndpoints[_SpotifyArtistLibraryEndpoints],
    ItemReadEndpoints[SpotifyResourceURI, SpotifyArtistCollection],
    BatchReadEndpoints[SpotifyResourceURI, SpotifyArtistCollection],
    CollectionReadEndpoints[SpotifyResourceURI, SpotifyArtistCollection, SpotifyAlbum],
):
    __final__ = True

    _read_url: ClassVar[URL] = API_URL.joinpath("artists")
    _read_limit: ClassVar[int] = 50
    _read_path: ClassVar[str] = "artists"

    _extend_path: ClassVar[str] = "items"

    @ApiURLSchema.validate_call()  # WORKAROUND: replace with @validate_call when supported
    async def get(self, url: ApiURL[SpotifyResourceURI, SpotifyArtist]) -> SpotifyArtistCollection:
        response = await self._handler.get(url)
        self._add_albums_cursor_to_item(response)
        return type(self).create_model(response, context=self._model_context)

    @validate_call
    async def get_all_items(
            self,
            collection: SpotifyArtistCollection | PageCursor,
            types: set[OnErrorOmit[_ALBUM_TYPE]] = _ALL_ALBUM_TYPES,
    ) -> list[SpotifyAlbum]:
        match collection:
            case PageCursor() as cursor:
                pass
            case SpotifyArtistCollection() as artist:
                cursor = artist.cursor

        query = {"include_groups": ",".join(map(str, types))}
        cursor.url = cursor.url.update_query(query)
        return await super().get_all_items(cursor)
