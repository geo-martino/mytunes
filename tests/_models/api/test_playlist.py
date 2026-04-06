from collections.abc import Generator, Callable
from unittest.mock import patch, Mock, AsyncMock

import pytest
from aiorequestful.request import RequestHandler
from faker import Faker
from yarl import URL

from musify._models.api.playlist import PlaylistBatchReadAllEndpoints, PlaylistLibraryEndpoints, \
    PlaylistReadWriteEndpoints
from musify._models.collection.playlist import RemotePlaylist, Playlist
from musify._models.item.user import RemoteUser
from musify._models.properties.uri import URI
from musify._models.remote import RemoteResource
from tests.remote import SimpleURI, MockRemoteResource, MockUrlCursor
from tests.testers import URI_TYPE_CONVERTERS, EndpointsTester


@pytest.fixture
def playlists(playlists: list[Playlist], faker: Faker) -> list[RemotePlaylist]:
    return [
        RemotePlaylist(
            **pl.model_dump(),
            owner=RemoteUser(name=faker.name(), uri=SimpleURI.create_random(RemoteUser.type)),
            cursor=MockUrlCursor(url=faker.url()),
            uri=SimpleURI.create_random(RemotePlaylist.type))
        for pl in playlists
    ]


class TestPlaylistReadWriteEndpoints(EndpointsTester):
    class MockPlaylistReadWriteEndpoints(PlaylistReadWriteEndpoints[SimpleURI, MockRemoteResource, MockRemoteResource]):
        _write_limit = 18

    @pytest.fixture
    def model(self, handler: RequestHandler) -> MockPlaylistReadWriteEndpoints:
        return self.MockPlaylistReadWriteEndpoints(handler=handler)

    @pytest.mark.parametrize("converter", URI_TYPE_CONVERTERS.values(), ids=URI_TYPE_CONVERTERS.keys())
    async def test_add_and_skip_duplicates(
            self,
            model: PlaylistReadWriteEndpoints,
            uri: URI,
            uris: list[URI],
            mock_get: Mock,
            faker: Faker,
            converter: Callable[[URI], str | URI | URL | RemoteResource],
    ):
        uris_duplicated = uris + uris[:faker.random_int(1, len(uris))]
        uris_collection = [
            uris.pop(faker.random_int(0, len(uris) - 1)) for _ in range(faker.random_int(1, len(uris) - 10))
        ]

        assert sorted(uris_collection) != sorted(uris)
        assert sorted(uris_duplicated) != sorted(uris)

        url = converter(uri)
        limit = faker.random_int(1)
        uris_duplicated = list(map(self._convert_uri_to_random_input_type, uris_duplicated))
        collection_items = [MockRemoteResource(uri=uri) for uri in uris_collection]

        # we just want to test that duplicates are skipped when adding, so we mock all surrounding logic
        with (
            patch.object(PlaylistReadWriteEndpoints, "get_all", return_value=collection_items, new_callable=AsyncMock),
            patch.object(PlaylistReadWriteEndpoints, "add", new_callable=AsyncMock) as mock_add
        ):
            await model.add_and_skip_duplicates(url, uris_duplicated, limit=limit)
            mock_add.assert_called_once_with(uri.api_url, uris, limit=limit)


@pytest.fixture
def mock_get_all(playlists: list[RemotePlaylist], faker: Faker) -> Generator[Mock, None, None]:
    with patch.object(PlaylistBatchReadAllEndpoints, "get_all", return_value=playlists) as mock_get_all:
        yield mock_get_all


class TestPlaylistBatchReadAllEndpoints(EndpointsTester):
    @pytest.fixture
    def model(self, handler: RequestHandler) -> PlaylistBatchReadAllEndpoints:
        return PlaylistBatchReadAllEndpoints(handler=handler)

    async def test_get_by_user(
            self,
            model: PlaylistBatchReadAllEndpoints,
            playlists: list[RemotePlaylist],
            mock_get_all: Mock,
            faker: Faker
    ):
        expected = faker.random_elements(playlists, unique=True)
        owner = expected[0].owner
        for pl in expected:
            pl.owner = owner

        assert sorted(await model.get_by_user(user=owner)) == sorted(expected)

    async def test_get_by_name(
            self,
            model: PlaylistBatchReadAllEndpoints,
            playlists: list[RemotePlaylist],
            mock_get_all: Mock,
            faker: Faker
    ):
        expected = faker.random_element(playlists)
        assert await model.get_by_name(name=expected.name) == expected

    async def test_get_by_names(
            self,
            model: PlaylistBatchReadAllEndpoints,
            playlists: list[RemotePlaylist],
            mock_get_all: Mock,
            faker: Faker
    ):
        expected = faker.random_elements(playlists, unique=True)
        assert await model.get_by_names(names=[pl.name for pl in expected]) == expected


class TestPlaylistLibraryEndpoints(EndpointsTester):
    @pytest.fixture
    def model(self, handler: RequestHandler) -> PlaylistLibraryEndpoints:
        return PlaylistLibraryEndpoints(handler=handler)

    @pytest.fixture
    def mock_create(self) -> Generator[Mock, None, None]:
        with patch.object(PlaylistLibraryEndpoints, "create") as mock_create:
            yield mock_create

    async def test_get_or_create_gets_existing(
            self,
            model: PlaylistLibraryEndpoints,
            playlists: list[RemotePlaylist],
            mock_get_all: Mock,
            mock_create: Mock,
            faker: Faker,
    ):
        expected = faker.random_element(playlists)
        name = expected.name
        kwargs = dict(description=faker.sentence())

        assert await model.get_or_create(name=name, **kwargs) is expected
        mock_create.assert_not_called()

    async def test_get_or_create_creates_new(
            self,
            model: PlaylistLibraryEndpoints,
            playlists: list[RemotePlaylist],
            mock_get_all: Mock,
            mock_create: Mock,
            faker: Faker
    ):
        name = None
        current_names = {pl.name for pl in playlists}
        while name is None or name in current_names:
            name = faker.word()

        kwargs = dict(description=faker.sentence())

        await model.get_or_create(name=name, **kwargs)
        mock_create.assert_called_once_with(name=name, **kwargs)
