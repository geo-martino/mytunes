from typing import ClassVar, final

from pydantic import AliasPath, PositiveInt
from yarl import URL

from musify.models.api import HasSavedEndpoints
from musify.models.api.track import TrackReadItemEndpoints, TrackReadItemsEndpoints, \
    TrackReadSavedEndpoints, TrackWriteSavedEndpoints
from musify.models.api.types import _ApiURISchema
from musify.spotify import API_URL
from musify.spotify.api._base import SpotifyEndpoints
from musify.spotify.api._types import SpotifyApiURI, SpotifyApiURISequence
from musify.spotify.item.track import SpotifyTrack, SpotifyAudioFeatures, SpotifyAudioAnalysis
from musify.spotify.properties.uri import SpotifyResourceURI


@final
class _SpotifySavedTrackEndpoints(
    SpotifyEndpoints[SpotifyResourceURI, SpotifyTrack],
    TrackReadSavedEndpoints[SpotifyResourceURI, SpotifyTrack],
    TrackWriteSavedEndpoints[SpotifyResourceURI, SpotifyTrack],
):
    __final__ = True

    _saved_read_url: ClassVar[URL] = API_URL.joinpath("me/tracks")
    _saved_write_url: ClassVar[URL] = API_URL.joinpath("me/library")
    _saved_limit: ClassVar[int] = 50
    _saved_path: ClassVar[AliasPath] = AliasPath("items", "*", "track")

    _batch_limit: ClassVar[int] = 50


@final
class SpotifyTrackEndpoints(
    SpotifyEndpoints[SpotifyResourceURI, SpotifyTrack],
    HasSavedEndpoints[_SpotifySavedTrackEndpoints],
    TrackReadItemEndpoints[SpotifyResourceURI, SpotifyTrack],
    TrackReadItemsEndpoints[SpotifyResourceURI, SpotifyTrack],
):
    __final__ = True

    _many_url: ClassVar[URL] = API_URL.joinpath("tracks")
    _many_limit: ClassVar[int] = 50
    _many_path: ClassVar[str] = "tracks"

    @_ApiURISchema.validate_call()  # WORKAROUND: replace with @validate_call when supported
    async def get_audio_features(self, uri: SpotifyApiURI[SpotifyTrack]) -> SpotifyAudioFeatures:
        """Get the audio features for a given track"""
        url = API_URL.joinpath("audio-features", uri.id)
        response = await self._handler.get(url)
        return SpotifyAudioFeatures.model_validate(response)

    @_ApiURISchema.validate_call("uris", is_sequence=True)  # WORKAROUND: replace with @validate_call when supported
    async def get_many_audio_features(
            self, uris: SpotifyApiURISequence[SpotifyTrack], limit: PositiveInt = 100
    ) -> list[SpotifyAudioFeatures]:
        """Get the audio features for a given track"""
        url = API_URL.joinpath("audio-features")
        ids = (uri.id for uri in uris)

        items = []
        for batch in self._batch_values(ids, limit):
            params = {"ids": ",".join(batch)}
            response = await self._handler.get(url, params=params)
            items.extend(map(SpotifyAudioFeatures.model_validate, response["audio_features"]))

        return items

    @_ApiURISchema.validate_call()  # WORKAROUND: replace with @validate_call when supported
    async def get_audio_analysis(self, uri: SpotifyApiURI[SpotifyTrack]) -> SpotifyAudioAnalysis:
        """Get the audio analysis for a given track"""
        url = API_URL.joinpath("audio-analysis", uri.id)
        response = await self._handler.get(url)
        return SpotifyAudioAnalysis.model_validate(response)
