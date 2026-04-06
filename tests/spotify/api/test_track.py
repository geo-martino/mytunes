from collections.abc import Generator
from typing import Any
from unittest.mock import patch, AsyncMock, Mock

import math
import pytest
from aiorequestful.request import RequestHandler
from faker import Faker
from yarl import URL

from musify.spotify import API_URL
# noinspection PyProtectedMember
from musify.spotify._api.track import SpotifyTrackEndpoints
from musify.spotify._item.track import SpotifyAudioFeatures, SpotifyAudioAnalysis
from musify.spotify._properties.uri import SpotifyResourceURI
from tests.spotify.generator import SpotifyPayloadGenerator
from tests.testers import BaseModelTester


class TestSpotifyTrackEndpoints(BaseModelTester):
    @pytest.fixture
    def model(self, handler: RequestHandler) -> SpotifyTrackEndpoints:
        return SpotifyTrackEndpoints.model_validate(handler)

    @pytest.fixture
    def uri(self, faker: Faker) -> SpotifyResourceURI:
        return SpotifyResourceURI.from_id(faker.pystr(22, 22), kind="track")

    @pytest.fixture
    def uris(self, faker: Faker) -> list[SpotifyResourceURI]:
        return [
            SpotifyResourceURI.from_id(faker.pystr(22, 22), kind="track")
            for _ in range(faker.random_int(1, 50))
        ]

    @pytest.fixture
    def mock_get_features(self, generator: SpotifyPayloadGenerator) -> Generator[Mock, None, None]:
        def _generate_payload(url: URL, *_, **__) -> dict[str, Any]:
            track_id = url.path.split("/")[-1]
            return generator.generate_audio_features(track_id)

        with patch.object(RequestHandler, "get", side_effect=_generate_payload, new_callable=AsyncMock) as mock_get:
            yield mock_get

    async def test_get_audio_features(
            self,
            model: SpotifyTrackEndpoints,
            uri: SpotifyResourceURI,
            mock_get_features: Mock,
    ):
        model = await model.get_audio_features(uri)
        mock_get_features.assert_called_with(API_URL.joinpath("audio-features", uri.id))
        assert isinstance(model, SpotifyAudioFeatures)
        assert model.uri == uri

    @pytest.fixture
    def mock_get_many_features(self, generator: SpotifyPayloadGenerator) -> Generator[Mock, None, None]:
        # noinspection PyUnusedLocal
        def _generate_payload(url: URL, params: dict[str, Any], *_, **__) -> dict[str, Any]:
            track_ids = params["ids"].split(",")
            return {"audio_features": [generator.generate_audio_features(track_id) for track_id in track_ids]}

        with patch.object(RequestHandler, "get", side_effect=_generate_payload, new_callable=AsyncMock) as mock_get:
            yield mock_get

    async def test_get_many_audio_features(
            self,
            model: SpotifyTrackEndpoints,
            uris: list[SpotifyResourceURI],
            mock_get_many_features: Mock,
            faker: Faker,
    ):
        limit = faker.random_int(1, 10)
        expected = math.ceil(len(uris) / limit)

        results = await model.get_many_audio_features(uris, limit=limit)
        assert all(isinstance(result, SpotifyAudioFeatures) for result in results)
        assert len(results) == len(uris)
        assert sorted(result.uri for result in results) == sorted(uris)

        assert mock_get_many_features.call_count == expected

    @pytest.fixture
    def mock_get_analysis(self, generator: SpotifyPayloadGenerator) -> Generator[Mock, None, None]:
        def _generate_payload(*_, **__) -> dict[str, Any]:
            return generator.generate_audio_analysis()

        with patch.object(RequestHandler, "get", side_effect=_generate_payload, new_callable=AsyncMock) as mock_get:
            yield mock_get

    async def test_get_audio_analysis(
            self,
            model: SpotifyTrackEndpoints,
            uri: SpotifyResourceURI,
            mock_get_analysis: Mock,
    ):
        model = await model.get_audio_analysis(uri)
        mock_get_analysis.assert_called_with(API_URL.joinpath("audio-analysis", uri.id))
        assert isinstance(model, SpotifyAudioAnalysis)  # no id on this model so just check it's the right type
