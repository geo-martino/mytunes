from pydantic import Field, AliasPath

from musify.remote.collection.artist import RemoteArtistCollection
from musify.spotify.collection._base import SpotifyCollection
from musify.spotify.item.album import SpotifyAlbum
from musify.spotify.item.artist import SpotifyArtist
from musify.spotify.item.genre import SpotifyGenre
from musify.spotify.item.track import SpotifyTrack
from musify.spotify.properties.uri import SpotifyResourceURI


class SpotifyArtistCollection[AT: SpotifyAlbum, GT: SpotifyGenre](
    RemoteArtistCollection[str, SpotifyTrack, SpotifyResourceURI, AT, GT],
    SpotifyCollection,
    SpotifyArtist,
):
    albums: list[AT] = Field(
        description="The albums associated with this artist.",
        default_factory=list,
        validation_alias=AliasPath("albums", "items")
    )
