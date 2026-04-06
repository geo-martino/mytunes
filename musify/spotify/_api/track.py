from typing import ClassVar, final

from pydantic import AliasPath, PositiveInt
from yarl import URL

from musify.models.api import HasLibraryEndpoints, BatchReadAllEndpoints, BatchWriteEndpoints, ItemReadEndpoints, \
    BatchReadEndpoints
from musify.models.api.types import ApiURISchema
from musify.spotify import API_URL
from musify.spotify._api._base import SpotifyEndpoints, _SpotifyLibraryEndpoints
from musify.spotify._api._types import SpotifyApiURI, SpotifyApiURISequence
from .._item.track import SpotifyTrack, SpotifyAudioFeatures, SpotifyAudioAnalysis
from .._properties.uri import SpotifyResourceURI


@final
class _SpotifyTrackLibraryEndpoints(
    _SpotifyLibraryEndpoints[SpotifyResourceURI, SpotifyTrack],
    BatchReadAllEndpoints[SpotifyResourceURI, SpotifyTrack],
    BatchWriteEndpoints[SpotifyResourceURI, SpotifyTrack],
):
    __final__ = True

    _read_all_url: ClassVar[URL] = API_URL.joinpath("me/tracks")
    _read_all_limit: ClassVar[int] = 50
    _read_all_path: ClassVar[AliasPath] = AliasPath("items", "*", "track")

    _write_url: ClassVar[URL] = API_URL.joinpath("me/library")
    _write_limit: ClassVar[int] = 40


@final
class SpotifyTrackEndpoints(
    SpotifyEndpoints[SpotifyResourceURI, SpotifyTrack],
    HasLibraryEndpoints[_SpotifyTrackLibraryEndpoints],
    ItemReadEndpoints[SpotifyResourceURI, SpotifyTrack],
    BatchReadEndpoints[SpotifyResourceURI, SpotifyTrack],
):
    __final__ = True

    _read_url: ClassVar[URL] = API_URL.joinpath("tracks")
    _read_limit: ClassVar[int] = 50
    _read_path: ClassVar[str] = "tracks"

    @ApiURISchema.validate_call()  # WORKAROUND: replace with @validate_call when supported
    async def get_audio_features(self, uri: SpotifyApiURI[SpotifyTrack]) -> SpotifyAudioFeatures:
        """Get the audio features for a given track"""
        url = API_URL.joinpath("audio-features", uri.id)
        response = await self._handler.get(url)
        return SpotifyAudioFeatures.model_validate(response)

    @ApiURISchema.validate_call("uris", is_sequence=True)  # WORKAROUND: replace with @validate_call when supported
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

    @ApiURISchema.validate_call()  # WORKAROUND: replace with @validate_call when supported
    async def get_audio_analysis(self, uri: SpotifyApiURI[SpotifyTrack]) -> SpotifyAudioAnalysis:
        """Get the audio analysis for a given track"""
        url = API_URL.joinpath("audio-analysis", uri.id)
        response = await self._handler.get(url)
        return SpotifyAudioAnalysis.model_validate(response)
