from typing import final

from pydantic import Field, AliasPath

from musify.remote.collection.artist import RemoteArtistCollection
from musify.spotify.collection._base import SpotifyCollection
from musify.spotify.item.album import SpotifyAlbum
from musify.spotify.item.artist import SpotifyArtist
from musify.spotify.item.genre import SpotifyGenre
from musify.spotify.item.track import SpotifyTrack
from musify.spotify.properties.uri import SpotifyResourceURI


@final
class SpotifyArtistCollection[AT: SpotifyAlbum](
    RemoteArtistCollection[str, SpotifyTrack, AT, SpotifyGenre, SpotifyResourceURI],
    SpotifyArtist,
    SpotifyCollection,
):
    __final__ = True

    albums: list[AT] = Field(
        description="The albums associated with this artist.",
        default_factory=list,
        validation_alias=AliasPath("albums", "items")
    )
    total: int = Field(
        description="The total number of albums by this artist.",
        validation_alias=AliasPath("albums", "total")
    )
