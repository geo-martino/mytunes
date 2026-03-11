import math
from unittest.mock import patch, AsyncMock

import pytest
from aiorequestful.request import RequestHandler
from faker import Faker

from musify.spotify import API_URL
# noinspection PyProtectedMember
from musify.spotify.api._track import SpotifyTrackEndpoints
from musify.spotify.item.track import SpotifyAudioFeatures, SpotifyAudioAnalysis
from musify.spotify.properties.uri import SpotifyResourceURI
from tests.models.testers import BaseModelTester


class TestSpotifyTrackEndpoints(BaseModelTester):
    @pytest.fixture
    def model(self, handler: RequestHandler) -> SpotifyTrackEndpoints:
        return SpotifyTrackEndpoints.model_validate(handler)

    @pytest.fixture
    def uris(self, faker: Faker) -> list[SpotifyResourceURI]:
        return [
            SpotifyResourceURI.from_id(faker.pystr(22, 22), kind="track")
            for _ in range(faker.random_int(1, 50))
        ]

    async def test_get_audio_features(
            self,
            model: SpotifyTrackEndpoints,
            uris: list[SpotifyResourceURI],
            faker: Faker,
    ):
        uri = faker.random_element(uris)
        response = {"uri": str(uri)}

        with (
            patch.object(RequestHandler, "get", return_value=response, new_callable=AsyncMock) as mock_get,
            patch.object(SpotifyAudioFeatures, "model_validate") as mock_model_validate,
        ):
            await model.get_audio_features(uri)

            mock_get.assert_called_with(API_URL.joinpath("audio-features", uri.id))
            mock_model_validate.assert_called_with(mock_get.return_value)

    async def test_get_many_audio_features(
            self,
            model: SpotifyTrackEndpoints,
            uris: list[SpotifyResourceURI],
            faker: Faker,
    ):
        limit = faker.random_int(1, 10)
        expected = math.ceil(len(uris) / limit)

        def _return_response[T](*_, params: dict, **__) -> T:
            ids = params["ids"].split(",")
            return {"audio_features": [{"id": id_} for id_ in ids]}

        with (
            patch.object(RequestHandler, "get", side_effect=_return_response, new_callable=AsyncMock) as mock_get,
            patch.object(SpotifyAudioFeatures, "model_validate") as mock_model_validate,
        ):
            result = await model.get_many_audio_features(uris, limit=limit)
            assert len(result) == len(uris)

            assert mock_get.call_count == expected
            assert mock_model_validate.call_count == len(uris)

    async def test_get_audio_analysis(
            self,
            model: SpotifyTrackEndpoints,
            uris: list[SpotifyResourceURI],
            faker: Faker,
    ):
        uri = faker.random_element(uris)
        response = {"uri": str(uri)}

        with (
            patch.object(RequestHandler, "get", return_value=response, new_callable=AsyncMock) as mock_get,
            patch.object(SpotifyAudioAnalysis, "model_validate") as mock_model_validate,
        ):
            await model.get_audio_analysis(uri)

            mock_get.assert_called_with(API_URL.joinpath("audio-analysis", uri.id))
            mock_model_validate.assert_called_with(mock_get.return_value)
