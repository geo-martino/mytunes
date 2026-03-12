from unittest.mock import patch

import pytest
from aiohttp.web_protocol import RequestHandler
from faker import Faker

from musify.models.api import ReadCollectionEndpoints
# noinspection PyProtectedMember
from musify.spotify.api._artist import SpotifyArtistEndpoints
from musify.spotify.collection import SpotifyPageCursor
from musify.spotify.properties.uri import SpotifyResourceURI
from tests.models.testers import BaseModelTester


class TestSpotifyArtistEndpoints(BaseModelTester):
    @pytest.fixture
    def model(self, handler: RequestHandler) -> SpotifyArtistEndpoints:
        return SpotifyArtistEndpoints.model_validate(handler)

    async def test_get_all_adds_params(self, model: SpotifyArtistEndpoints, faker: Faker):
        uri = SpotifyResourceURI.from_id(faker.pystr(22, 22), kind="artist")
        cursor = SpotifyPageCursor(
            url=uri.api_url, limit=faker.random_int(0, 20), offset=0, total=faker.random_int(0, 50)
        )
        if faker.boolean():
            cursor.offset = cursor.total + 1

        types = set(faker.random_elements(("album", "single", "compilation", "appears_on"), unique=True))

        with patch.object(ReadCollectionEndpoints, "get_all"):
            await model.get_all(cursor, types=types)

            url = cursor.url if cursor.next is None else cursor.next.url
            assert sorted(url.query.get("include_groups", "").split(",")) == sorted(types)
