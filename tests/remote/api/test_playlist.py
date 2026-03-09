from collections.abc import Generator
from unittest.mock import patch, Mock

import pytest
from aiorequestful.request import RequestHandler
from faker import Faker

from musify.remote.api.playlist import PlaylistGetSavedEndpoints, PlaylistMutableSavedEndpoints
from musify.remote.collection import ItemsCursor
from musify.remote.collection.playlist import RemotePlaylist
from musify.remote.user import RemoteUser
from tests.remote.api.testers import RemoteEndpointsTester
from tests.utils import SimpleURI


@pytest.fixture
def playlists(faker: Faker) -> list[RemotePlaylist]:
    return [
        RemotePlaylist(
            name=faker.name(),
            owner=RemoteUser(
                name=faker.user_name(),
                uri=SimpleURI.from_id(faker.word(), kind=RemoteUser.type)
            ),
            uri=SimpleURI.from_id(faker.word(), kind=RemotePlaylist.type),
            total=faker.random_int(0, 100),
            cursor=ItemsCursor(current=faker.url())
        )
        for _ in range(faker.random_int(10, 30))
    ]


@pytest.fixture
def mock_get_all(playlists: list[RemotePlaylist], faker: Faker) -> Generator[Mock, None, None]:
    with patch.object(PlaylistGetSavedEndpoints, "get_all", return_value=playlists) as mock_get_all:
        yield mock_get_all


class TestPlaylistGetSavedEndpoints(RemoteEndpointsTester):
    @pytest.fixture
    def model(self, handler: RequestHandler) -> PlaylistGetSavedEndpoints:
        return PlaylistGetSavedEndpoints(handler=handler)

    async def test_get_by_user(
            self,
            model: PlaylistGetSavedEndpoints,
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
            model: PlaylistGetSavedEndpoints,
            playlists: list[RemotePlaylist],
            mock_get_all: Mock,
            faker: Faker
    ):
        expected = faker.random_element(playlists)
        assert await model.get_by_name(name=expected.name) == expected

    async def test_get_by_names(
            self,
            model: PlaylistGetSavedEndpoints,
            playlists: list[RemotePlaylist],
            mock_get_all: Mock,
            faker: Faker
    ):
        expected = faker.random_elements(playlists, unique=True)
        assert await model.get_by_names(names=[pl.name for pl in expected]) == expected


class TestPlaylistMutableSavedEndpoints(RemoteEndpointsTester):
    @pytest.fixture
    def model(self, handler: RequestHandler) -> PlaylistMutableSavedEndpoints:
        return PlaylistMutableSavedEndpoints(handler=handler)

    async def test_get_or_create_gets_existing(
            self,
            model: PlaylistMutableSavedEndpoints,
            playlists: list[RemotePlaylist],
            mock_get_all: Mock,
            faker: Faker
    ):
        expected = faker.random_element(playlists)
        name = expected.name
        kwargs = dict(description=faker.sentence())

        with patch.object(model.__class__, "create") as mock_create:
            assert await model.get_or_create(name=name, **kwargs) is expected
            mock_create.assert_not_called()

    async def test_get_or_create_creates_new(
            self,
            model: PlaylistMutableSavedEndpoints,
            playlists: list[RemotePlaylist],
            mock_get_all: Mock,
            faker: Faker
    ):
        name = None
        current_names = {pl.name for pl in playlists}
        while name is None or name in current_names:
            name = faker.word()

        kwargs = dict(description=faker.sentence())
        expected = "created_playlist"

        with patch.object(model.__class__, "create", return_value=expected) as mock_create:
            await model.get_or_create(name=name, **kwargs)
            mock_create.assert_called_once_with(name=name, **kwargs)
