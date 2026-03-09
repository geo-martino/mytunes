from typing import ClassVar, final

from aiorequestful.auth import Authoriser
from yarl import URL
from pydantic import AliasPath, Field

from musify.remote.api.track import TrackGetSingleEndpoints, TrackGetManyEndpoints, \
    TrackGetSavedEndpoints, TrackMutableSavedEndpoints
from musify.spotify import API_URL
from musify.spotify.item.track import SpotifyTrack
from musify.spotify.properties.uri import SpotifyResourceURI
from musify.spotify.api._base import SpotifyEndpoints


@final
class _SpotifySavedTrackEndpoints(
    SpotifyEndpoints[SpotifyResourceURI, SpotifyTrack],
    TrackGetSavedEndpoints[SpotifyResourceURI, SpotifyTrack],
    TrackMutableSavedEndpoints[SpotifyResourceURI, SpotifyTrack],
):
    __final__ = True

    _saved_url: ClassVar[URL] = API_URL.joinpath("me/tracks")
    _saved_limit: ClassVar[int] = 50
    _saved_path: ClassVar[AliasPath] = AliasPath("items", "*", "track")

    _batch_limit: ClassVar[int] = 50


@final
class SpotifyTrackEndpoints(
    SpotifyEndpoints[SpotifyResourceURI, SpotifyTrack],
    TrackGetSingleEndpoints[SpotifyResourceURI, SpotifyTrack],
    TrackGetManyEndpoints[SpotifyResourceURI, SpotifyTrack],
):
    __final__ = True

    _many_url: ClassVar[URL] = API_URL.joinpath("tracks")
    _many_limit: ClassVar[int] = 50
    _many_path: ClassVar[str] = "tracks"

    saved: _SpotifySavedTrackEndpoints = Field(
        description="Access endpoints for the current user's saved tracks.",
    )
