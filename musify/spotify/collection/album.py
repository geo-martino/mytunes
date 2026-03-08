from typing import final

from pydantic import Field, AliasPath, PositiveInt

from musify.remote.collection.album import RemoteAlbumCollection
from musify.spotify.collection._base import SpotifyCollection, SpotifyItemsCursor
from musify.spotify.item.album import SpotifyAlbum
from musify.spotify.item.artist import SpotifyArtist
from musify.spotify.item.genre import SpotifyGenre
from musify.spotify.item.track import SpotifyTrack
from musify.spotify.properties.uri import SpotifyResourceURI


# noinspection PyFinal
@final
class SpotifyAlbumCollection[RT: SpotifyArtist](
    RemoteAlbumCollection[SpotifyTrack, RT, SpotifyGenre, SpotifyResourceURI],
    SpotifyAlbum,
    SpotifyCollection,
):
    __final__ = True

    tracks: list[SpotifyTrack] = Field(
        description="The tracks on this album.",
        default_factory=list,
        validation_alias=AliasPath("tracks", "items")
    )

    total: PositiveInt = Field(
        description="The total number of tracks on this album.",
        validation_alias=AliasPath("tracks", "total")
    )
    cursor: SpotifyItemsCursor = Field(
        description=(
            "The cursor for the current page of tracks. "
            "This is used for pagination and should be passed to the next page request to extend the collection."
        ),
        validation_alias="tracks",
    )
