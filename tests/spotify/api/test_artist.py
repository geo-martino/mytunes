from collections.abc import Generator
from typing import Any
from unittest.mock import patch, AsyncMock, Mock

import pytest
from aiorequestful.request import RequestHandler
from faker import Faker
from yarl import URL

from musify.spotify import API_URL
# noinspection PyProtectedMember
from musify.spotify._api.artist import SpotifyArtistEndpoints
from musify.spotify._collection.artist import SpotifyArtistCollection
from musify.spotify._item.album import SpotifyAlbum
from musify.spotify._properties.uri import SpotifyResourceURI
from musify.spotify.cursors import SpotifyInitialCursor
from tests.spotify.generator import SpotifyPayloadGenerator
from tests.testers import BaseModelTester


class TestSpotifyArtistEndpoints(BaseModelTester):
    @pytest.fixture
    def model(self, handler: RequestHandler) -> SpotifyArtistEndpoints:
        return SpotifyArtistEndpoints.model_validate(handler)

    @pytest.fixture
    def uri(self, faker: Faker) -> SpotifyResourceURI:
        return SpotifyResourceURI.from_id(faker.pystr(22, 22), kind="artist")

    @pytest.fixture
    def uris(self, faker: Faker) -> list[SpotifyResourceURI]:
        return [
            SpotifyResourceURI.from_id(faker.pystr(22, 22), kind="artist")
            for _ in range(faker.random_int(1, 50))
        ]

    @pytest.fixture
    def mock_get(self, generator: SpotifyPayloadGenerator) -> Generator[Mock, None, None]:
        def _generate_payload(url: URL, *_, **__) -> dict[str, Any]:
            artist_id = url.path.split("/")[-1]
            return generator.generate_artist(artist_id)

        with patch.object(RequestHandler, "get", side_effect=_generate_payload, new_callable=AsyncMock) as mock_get:
            yield mock_get

    async def test_get(self, model: SpotifyArtistEndpoints, uri: SpotifyResourceURI, mock_get: Mock):
        model = await model.get(uri)
        mock_get.assert_called_with(API_URL.joinpath("artists", uri.id))
        assert isinstance(model, SpotifyArtistCollection)
        assert model.uri == uri

    @pytest.fixture
    def mock_get_all(self, generator: SpotifyPayloadGenerator, faker: Faker) -> Generator[Mock, None, None]:
        def _generate_payload(url: URL, *_, **__) -> dict[str, Any]:
            items = [generator.generate_album() for _ in range(faker.random_int(1, 50))]
            return {"href": str(url), "items": items}

        with patch.object(RequestHandler, "get", side_effect=_generate_payload, new_callable=AsyncMock) as mock_get:
            yield mock_get

    async def test_get_all_adds_params(
            self, model: SpotifyArtistEndpoints, uri: SpotifyResourceURI, mock_get_all: Mock, faker: Faker
    ):
        uri = SpotifyResourceURI.from_id(faker.pystr(22, 22), kind="artist")
        cursor = SpotifyInitialCursor(url=uri.api_url, total=faker.random_int(0, 50))
        types = set(faker.random_elements(("album", "single", "compilation", "appears_on"), unique=True))

        print(type(model))
        print(type(model).item_type_adapter)
        results = await model.get_all(cursor, types=types)
        assert all(isinstance(result, SpotifyAlbum) for result in results)

        url = URL(mock_get_all.call_args.args[0])
        assert sorted(cursor.url.query.get("include_groups", "").split(",")) == sorted(types)
        assert sorted(url.query.get("include_groups", "").split(",")) == sorted(types)
