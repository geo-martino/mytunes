from collections.abc import Generator
from unittest.mock import patch, Mock

import pytest
from aiorequestful.request import RequestHandler
from faker import Faker

from musify.models.api.playlist import PlaylistReadSavedEndpoints, PlaylistReadWriteSavedEndpoints
from musify.models.collection.playlist import RemotePlaylist
from musify.models.user import RemoteUser
from tests.models.api.testers import EndpointsTester
from tests.models.api.utils import MockUrlCursor
from tests.utils import SimpleURI


@pytest.fixture
def mock_get_all(playlists: list[RemotePlaylist], faker: Faker) -> Generator[Mock, None, None]:
    with patch.object(PlaylistReadSavedEndpoints, "get_all", return_value=playlists) as mock_get_all:
        yield mock_get_all


class TestPlaylistReadSavedEndpoints(EndpointsTester):
    @pytest.fixture
    def model(self, handler: RequestHandler) -> PlaylistReadSavedEndpoints:
        return PlaylistReadSavedEndpoints(handler=handler)

    async def test_get_by_user(
            self,
            model: PlaylistReadSavedEndpoints,
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
            model: PlaylistReadSavedEndpoints,
            playlists: list[RemotePlaylist],
            mock_get_all: Mock,
            faker: Faker
    ):
        expected = faker.random_element(playlists)
        assert await model.get_by_name(name=expected.name) == expected

    async def test_get_by_names(
            self,
            model: PlaylistReadSavedEndpoints,
            playlists: list[RemotePlaylist],
            mock_get_all: Mock,
            faker: Faker
    ):
        expected = faker.random_elements(playlists, unique=True)
        assert await model.get_by_names(names=[pl.name for pl in expected]) == expected


class TestPlaylistWriteSavedEndpoints(EndpointsTester):
    @pytest.fixture
    def model(self, handler: RequestHandler) -> PlaylistReadWriteSavedEndpoints:
        return PlaylistReadWriteSavedEndpoints(handler=handler)

    async def test_get_or_create_gets_existing(
            self,
            model: PlaylistReadWriteSavedEndpoints,
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
            model: PlaylistReadWriteSavedEndpoints,
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
