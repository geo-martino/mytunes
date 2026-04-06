import pytest
from aiohttp.web_protocol import RequestHandler
from faker import Faker

from musify.models import ResourceModel
from musify.models.collection.playlist import Playlist
from musify.models.item.album import Album
from musify.models.item.artist import Artist
from musify.models.item.track import Track
# noinspection PyProtectedMember
from musify.spotify._api.search import SpotifySearchEndpoints
from musify.spotify._item.artist import SpotifyArtist
from musify.spotify._item.track import SpotifyTrack
from tests.models.testers import BaseModelTester


class TestSpotifySearchEndpoints(BaseModelTester):
    @pytest.fixture
    def model(self, handler: RequestHandler) -> SpotifySearchEndpoints:
        return SpotifySearchEndpoints.model_validate(handler)

    async def test_format_query_params(self, model: SpotifySearchEndpoints, faker: Faker):
        query = "track:track name artist:artist name"
        types = {SpotifyTrack.type, SpotifyArtist.type}

        result = model._format_query_params(query=query, types=types)
        assert result["q"] == query
        assert set(result["type"].split(",")) == types
        assert "limit" not in result
        assert "offset" not in result

        limit = faker.random_int(min=1, max=50)
        offset = faker.random_int(min=1, max=1000)
        result = model._format_query_params(query=query, types=types, limit=limit, offset=offset)
        assert result["limit"] == limit
        assert result["offset"] == offset

    @staticmethod
    def assert_format_query_from_item(
            model: SpotifySearchEndpoints, item: ResourceModel, expected_query: str, faker: Faker
    ):
        additional = {"limit": faker.random_int(), "offset": faker.random_int()}

        result = model._format_query_from_item(item=item, **additional)
        assert result.pop("query") == expected_query
        assert result.pop("types") == {item.type}
        assert result == additional

    async def test_format_query_from_track(self, model: SpotifySearchEndpoints, faker: Faker):
        item = Track(name=faker.word(), artists=[faker.word() for _ in range(3)])
        expected_query = f"track:{item.name} artist:{item.artists[0].name}"

        self.assert_format_query_from_item(model=model, item=item, expected_query=expected_query, faker=faker)

    async def test_format_query_from_track_with_no_artists(self, model: SpotifySearchEndpoints, faker: Faker):
        item = Track(name=faker.word())
        expected_query = item.name

        self.assert_format_query_from_item(model=model, item=item, expected_query=expected_query, faker=faker)

    async def test_format_query_from_album(self, model: SpotifySearchEndpoints, faker: Faker):
        item = Album(name=faker.word(), artists=[faker.word() for _ in range(3)])
        expected_query = f"album:{item.name} artist:{item.artists[0].name}"

        self.assert_format_query_from_item(model=model, item=item, expected_query=expected_query, faker=faker)

    async def test_format_query_from_album_with_no_artists(self, model: SpotifySearchEndpoints, faker: Faker):
        item = Album(name=faker.word())
        expected_query = item.name

        self.assert_format_query_from_item(model=model, item=item, expected_query=expected_query, faker=faker)

    async def test_format_query_from_artist(self, model: SpotifySearchEndpoints, faker: Faker):
        item = Artist(name=faker.word(), album=faker.word())
        expected_query = item.name

        self.assert_format_query_from_item(model=model, item=item, expected_query=expected_query, faker=faker)

    async def test_format_query_from_playlist(self, model: SpotifySearchEndpoints, faker: Faker):
        item = Playlist(name=faker.word())
        expected_query = model.cleaner.clean(item.name) if model.cleaner is not None else item.name

        self.assert_format_query_from_item(model=model, item=item, expected_query=expected_query, faker=faker)
