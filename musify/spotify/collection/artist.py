from typing import final, Annotated, TYPE_CHECKING

from pydantic import Field, AliasPath, model_validator

from musify.models.api.artist import HasArtistEndpoints
from musify.models.collection.artist import RemoteArtistCollection
from musify.models.metadata import Attribute
from musify.spotify.cursors import SpotifyIndexCursor, SpotifyInitialCursor
from musify.spotify.item.album import SpotifyAlbum
from musify.spotify.item.artist import SpotifyArtist
from musify.spotify.item.genre import SpotifyGenre
from musify.spotify.properties.length import HasSpotifyLength
from musify.spotify.properties.uri import SpotifyResourceURI

if TYPE_CHECKING:
    # noinspection PyProtectedMember
    from musify.spotify.api._artist import _ALL_ALBUM_TYPES, _ALBUM_TYPE, SpotifyArtistEndpoints



# noinspection PyFinal
@final
class SpotifyArtistCollection[AT: SpotifyAlbum](
    SpotifyArtist,
    RemoteArtistCollection[SpotifyResourceURI, AT, SpotifyGenre, SpotifyIndexCursor | SpotifyInitialCursor],
    HasSpotifyLength,
):
    __final__ = True

    albums: Annotated[list[AT], Attribute()] = Field(
        description="The albums associated with this artist.",
        default_factory=list,
        validation_alias=AliasPath("albums", "items"),
        repr=False,
    )

    # the implementation of SpotifyArtistEndpoints adds a 'starter' cursor to get albums for each artist
    # in the response, therefore we need to support an InitialCursor here to support this
    cursor: Annotated[SpotifyIndexCursor | SpotifyInitialCursor, Attribute()] = Field(
        description=(
            "The cursor for the current page of tracks. "
            "This is used for pagination and should be passed to the next page request to extend the collection."
        ),
        validation_alias="albums",
        union_mode="left_to_right",
    )

    @model_validator(mode="before")
    @classmethod
    def _reformat_albums_from_response(cls, data: dict) -> dict:
        # the validation alias and name for these are the same
        # we need to reformat the data to fit the model better if the cursor is present in the response without items
        if "albums" in data and isinstance(data["albums"], dict) and "items" not in data["albums"]:
            data["cursor"] = data.pop("albums")
        return data

    async def reload_items(
            self,
            api: HasArtistEndpoints[SpotifyArtistEndpoints],
            types: set[_ALBUM_TYPE] | None = None,
    ) -> None:
        # Need to use this logic instead of setting as default due to cyclical imports
        # noinspection PyProtectedMember
        from musify.spotify.api._artist import _ALL_ALBUM_TYPES
        if types is None:
            types = set(_ALL_ALBUM_TYPES)

        cursor = SpotifyInitialCursor(**self.cursor.model_dump())
        self._clear()

        # WORKAROUND: Spotify API does not return all album when requesting a combination of album types
        #  it only returns all albums if each album type is requested individually
        for album_type in types:
            self.albums.extend(await api.artists.get_all(cursor, types={album_type}))
