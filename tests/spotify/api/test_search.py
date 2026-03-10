import pytest
from aiohttp.web_protocol import RequestHandler
from faker import Faker

from musify.models.collection.playlist import Playlist
from musify.models.item.album import Album
from musify.models.item.artist import Artist
from musify.models.item.track import Track
# noinspection PyProtectedMember
from musify.spotify.api._search import SpotifySearchEndpoints
from tests.models.testers import MusifyModelTester


class TestSpotifySearchEndpoints(MusifyModelTester):
    @pytest.fixture
    def model(self, handler: RequestHandler) -> SpotifySearchEndpoints:
        return SpotifySearchEndpoints.model_validate(handler)

    async def test_format_query_params(self, model: SpotifySearchEndpoints, faker: Faker):
        query = "track:track name artist:artist name"
        types = {"track", "artist"}

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

    async def test_format_query_from_track(self, model: SpotifySearchEndpoints, faker: Faker):
        item = Track(name=faker.word(), artists=[faker.word() for _ in range(3)])
        kwargs = {"limit": faker.random_int(), "offset": faker.random_int()}

        result = model._format_query_from_item(item=item, **kwargs)
        assert result.pop("query") == f"track:{item.name} artist:{item.artists[0].name}"
        assert result.pop("types") == {"tracks"}
        assert result == kwargs

    async def test_format_query_from_album(self, model: SpotifySearchEndpoints, faker: Faker):
        item = Album(name=faker.word(), artists=[faker.word() for _ in range(3)])
        kwargs = {"limit": faker.random_int(), "offset": faker.random_int()}

        result = model._format_query_from_item(item=item, **kwargs)
        assert result.pop("query") == f"album:{item.name} artist:{item.artists[0].name}"
        assert result.pop("types") == {"albums"}
        assert result == kwargs

    async def test_format_query_from_artist(self, model: SpotifySearchEndpoints, faker: Faker):
        item = Artist(name=faker.word(), album=faker.word())
        kwargs = {"limit": faker.random_int(), "offset": faker.random_int()}

        result = model._format_query_from_item(item=item, **kwargs)
        assert result.pop("query") == item.name
        assert result.pop("types") == {"artists"}
        assert result == kwargs

    async def test_format_query_from_playlist(self, model: SpotifySearchEndpoints, faker: Faker):
        item = Playlist(name=faker.word())
        kwargs = {"limit": faker.random_int(), "offset": faker.random_int()}

        result = model._format_query_from_item(item=item, **kwargs)
        assert result.pop("query") == item.name
        assert result.pop("types") == {"playlists"}
        assert result == kwargs
