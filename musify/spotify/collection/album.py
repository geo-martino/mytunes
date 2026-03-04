from typing import final, Self

from pydantic import Field, AliasPath, model_validator

from musify.remote.collection.album import RemoteAlbumCollection
from musify.spotify.collection._base import SpotifyCollection
from musify.spotify.item.album import SpotifyAlbum
from musify.spotify.item.artist import SpotifyArtist
from musify.spotify.item.genre import SpotifyGenre
from musify.spotify.item.track import SpotifyTrack
from musify.spotify.properties.uri import SpotifyResourceURI


@final
class SpotifyAlbumCollection[RT: SpotifyArtist, GT: SpotifyGenre](
    RemoteAlbumCollection[str, SpotifyTrack, SpotifyResourceURI, RT, GT],
    SpotifyCollection,
    SpotifyAlbum,
):
    __final__ = True

    tracks: list[SpotifyTrack] = Field(
        description="The tracks on this album.",
        default_factory=list,
        validation_alias=AliasPath("tracks", "items")
    )
