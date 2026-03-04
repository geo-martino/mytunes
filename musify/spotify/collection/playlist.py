from pydantic import AliasPath, Field

from musify.models.sequence import MusifySequence, MusifyMutableSequence
from musify.remote.collection.playlist import RemotePlaylist, RemoteMutablePlaylist
from musify.spotify.collection._base import SpotifyCollection
from musify.spotify.item.track import SpotifyTrack
from musify.spotify.properties.images import HasSpotifyImages
from musify.spotify.properties.uri import SpotifyResourceURI


class SpotifyPlaylist(
    RemotePlaylist[str, SpotifyTrack, SpotifyResourceURI],
    SpotifyCollection,
    HasSpotifyImages,
):
    tracks: MusifySequence[str, SpotifyTrack] = Field(
        description="The tracks in this playlist.",
        default_factory=MusifySequence[str, SpotifyTrack],
        validation_alias=AliasPath("items", "items")
    )


class SpotifyMutablePlaylist(
    RemoteMutablePlaylist[str, SpotifyTrack, SpotifyResourceURI],
    SpotifyPlaylist,
):
    tracks: MusifyMutableSequence[str, SpotifyTrack] = Field(
        description="The tracks in this playlist.",
        default_factory=MusifyMutableSequence[str, SpotifyTrack],
        validation_alias=AliasPath("items", "items")
    )
