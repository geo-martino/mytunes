from typing import final

from pydantic import Field, AliasPath, PositiveInt, model_validator

from musify.models.collection.artist import RemoteArtistCollection
from musify.spotify.collection._base import SpotifyCollection, SpotifyItemsCursor
from musify.spotify.item.album import SpotifyAlbum
from musify.spotify.item.artist import SpotifyArtist
from musify.spotify.item.genre import SpotifyGenre
from musify.spotify.item.track import SpotifyTrack
from musify.spotify.properties.uri import SpotifyResourceURI


# noinspection PyFinal
@final
class SpotifyArtistCollection[AT: SpotifyAlbum](
    RemoteArtistCollection[str, SpotifyTrack, AT, SpotifyGenre, SpotifyResourceURI, SpotifyItemsCursor],
    SpotifyArtist,
    SpotifyCollection[AT],
):
    __final__ = True

    albums: list[AT] = Field(
        description="The albums associated with this artist.",
        default_factory=list,
        validation_alias=AliasPath("albums", "items"),
    )

    total: PositiveInt | None = Field(
        description="The total number of albums by this artist.",
        default=None,
        validation_alias=AliasPath("albums", "total"),
    )
    cursor: SpotifyItemsCursor = Field(
        description=(
            "The cursor for the current page of tracks. "
            "This is used for pagination and should be passed to the next page request to extend the collection."
        ),
        validation_alias="albums",
    )

    @model_validator(mode="before")
    @classmethod
    def _reformat_albums_from_response(cls, data: dict) -> dict:
        # the validation alias and name for these are the same
        # we need to reformat the data to fit the model better if only the cursor is present in the response
        if "albums" in data and isinstance(data["albums"], dict):
            data["cursor"] = data.pop("albums")
        return data
