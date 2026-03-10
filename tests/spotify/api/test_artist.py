from unittest.mock import patch

import pytest
from aiohttp.web_protocol import RequestHandler
from faker import Faker

from musify.remote.api import ReadCollectionEndpoints
# noinspection PyProtectedMember
from musify.spotify.api._artist import SpotifyArtistEndpoints
from musify.spotify.collection import SpotifyItemsCursor
from musify.spotify.properties.uri import SpotifyResourceURI
from tests.models.testers import MusifyModelTester


class TestSpotifyArtistEndpoints(MusifyModelTester):
    @pytest.fixture
    def model(self, handler: RequestHandler) -> SpotifyArtistEndpoints:
        return SpotifyArtistEndpoints.model_validate(handler)

    async def test_get_all_adds_params(self, model: SpotifyArtistEndpoints, faker: Faker):
        uri = SpotifyResourceURI.from_id(faker.pystr(22, 22), kind="artist")
        cursor = SpotifyItemsCursor(current=uri.api_url)
        if faker.boolean():
            cursor.next = cursor.current

        types = set(faker.random_elements(("album", "single", "compilation", "appears_on"), unique=True))

        with patch.object(ReadCollectionEndpoints, "get_all"):
            await model.get_all(cursor, types=types)

            url = cursor.current if cursor.next is None else cursor.next
            assert sorted(url.query.get("include_groups", "").split(",")) == sorted(types)
