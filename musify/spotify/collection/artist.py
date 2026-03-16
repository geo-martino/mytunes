from typing import final

from pydantic import Field, AliasPath, PositiveInt, model_validator

from musify.models.collection.artist import RemoteArtistCollection
from musify.spotify.collection._base import SpotifyCollection
from musify.spotify.cursors import SpotifyIndexCursor, SpotifyInitialCursor
from musify.spotify.item.album import SpotifyAlbum
from musify.spotify.item.artist import SpotifyArtist
from musify.spotify.item.genre import SpotifyGenre
from musify.spotify.item.track import SpotifyTrack
from musify.spotify.properties.length import HasSpotifyLength
from musify.spotify.properties.uri import SpotifyResourceURI


# noinspection PyFinal
@final
class SpotifyArtistCollection[AT: SpotifyAlbum](
    SpotifyArtist,
    SpotifyCollection[AT],
    HasSpotifyLength,
    RemoteArtistCollection[AT, SpotifyGenre, SpotifyResourceURI, SpotifyIndexCursor | SpotifyInitialCursor],
):
    __final__ = True

    albums: list[AT] = Field(
        description="The albums associated with this artist.",
        default_factory=list,
        validation_alias=AliasPath("albums", "items"),
    )

    # the implementation of SpotifyArtistEndpoints adds a 'starter' cursor to get albums for each artist
    # in the response, therefore we need to support an InitialCursor here to support this
    cursor: SpotifyIndexCursor | SpotifyInitialCursor = Field(
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
