from collections.abc import Generator
from typing import ClassVar
from unittest.mock import patch, Mock, AsyncMock

import pytest
from aiorequestful.request import RequestHandler
from faker import Faker
from mytunes._models.api import RemoteAPI, RemoteAuthoriser, HasLibraryEndpoints, Endpoints, HasAPI
from mytunes._models.api.items import HasTrackEndpoints
from mytunes._models.api.playlist import HasPlaylistEndpoints, PlaylistReadWriteEndpoints, \
    PlaylistLibraryEndpoints, PlaylistBatchReadAllEndpoints
from mytunes._models.item.user import RemoteUser
from pydantic import ValidationError
from tests.remote import SimpleURI, MockRemoteAuthoriser, MockItemEndpoints, MockRemoteAPI
from tests.testers import BaseModelTester


@pytest.fixture
def authoriser() -> RemoteAuthoriser:
    return MockRemoteAuthoriser()


@pytest.fixture
def handler(authoriser: RemoteAuthoriser) -> RequestHandler:
    return RequestHandler.create(authoriser=authoriser.create_authoriser())


@pytest.fixture
def api() -> RemoteAPI:
    return MockRemoteAPI()


@pytest.fixture
def mock_get() -> Generator[Mock, None, None]:
    with patch.object(RequestHandler, "get", new_callable=AsyncMock) as mock_get:
        yield mock_get


@pytest.fixture(autouse=True)
def mock_create_model() -> Generator[Mock, None, None]:
    with patch.object(Endpoints, "create_model", side_effect=lambda x, *_, **__: x) as mock_create_model:
        yield mock_create_model


class TestRemoteAPI(BaseModelTester):
    @pytest.fixture
    def model(self, api: RemoteAPI) -> RemoteAPI:
        return api

    def test_from_handler(self, handler: RequestHandler):
        model = MockRemoteAPI.model_validate(handler)
        assert model.search._handler is handler
        assert model.users._handler is handler
        assert model.tracks._handler is handler
        assert model.artists._handler is handler
        assert model.albums._handler is handler
        assert model.playlists._handler is handler

    def test_from_authoriser(self, authoriser: RemoteAuthoriser):
        model = MockRemoteAPI.model_validate(authoriser)
        assert isinstance(model.search._handler, RequestHandler)
        assert isinstance(model.users._handler, RequestHandler)
        assert isinstance(model.tracks._handler, RequestHandler)
        assert isinstance(model.artists._handler, RequestHandler)
        assert isinstance(model.albums._handler, RequestHandler)
        assert isinstance(model.playlists._handler, RequestHandler)

    def test_from_credentials(self, authoriser: RemoteAuthoriser):
        model = MockRemoteAPI.model_validate(authoriser.model_dump())
        assert isinstance(model.search._handler, RequestHandler)
        assert isinstance(model.users._handler, RequestHandler)
        assert isinstance(model.tracks._handler, RequestHandler)
        assert isinstance(model.artists._handler, RequestHandler)
        assert isinstance(model.albums._handler, RequestHandler)
        assert isinstance(model.playlists._handler, RequestHandler)

    def test_checks_all_handlers_are_the_same(self):
        with pytest.raises(ValidationError, match="All endpoint models must use the same request handler"):
            MockRemoteAPI(
                search=RequestHandler.create(),
                users=RequestHandler.create(),
                tracks=RequestHandler.create(),
                artists=RequestHandler.create(),
                albums=RequestHandler.create(),
                playlists=RequestHandler.create(),
            )

    @pytest.fixture
    def user(self, faker: Faker) -> RemoteUser:
        return RemoteUser(
            name=faker.name(), uri=SimpleURI.create_random(RemoteUser.type))

    @pytest.fixture(autouse=True)
    def mock_handler_context(self, handler: RequestHandler) -> Generator[Mock, None, None]:
        with patch.object(RequestHandler, "__aenter__", return_value=handler) as mock_context:
            yield mock_context

    async def test_context_sets_user_on_all_nested_endpoints(
            self, handler: RequestHandler, user: RemoteUser, mock_get: Mock
    ):
        api = MockRemoteAPI(handler=handler)
        assert api.users.user is None
        assert api.search.user is None
        assert api.tracks.user is None
        assert api.tracks.library.user is None
        assert api.artists.user is None
        assert api.artists.library.user is None
        assert api.albums.user is None
        assert api.albums.library.user is None
        assert api.playlists.user is None
        assert api.playlists.library.user is None

        mock_get.return_value = user

        async with api:
            assert api.users.user is user
            assert api.search.user is user
            assert api.tracks.user is user
            assert api.tracks.library.user is user
            assert api.artists.user is user
            assert api.artists.library.user is user
            assert api.albums.user is user
            assert api.albums.library.user is user
            assert api.playlists.user is user
            assert api.playlists.library.user is user


class TestHasAPI(BaseModelTester):
    class MockHasAPI(HasAPI):
        source: ClassVar[str] = "Test"

        @HasAPI._validate_api(
            "playlist",
            False,
            (None, HasPlaylistEndpoints, "{type} endpoints"),
            ("playlists", PlaylistReadWriteEndpoints, "writing data for {type}s"),
            ("playlists", HasLibraryEndpoints, "library {type}s endpoints"),
            ("playlists.library", PlaylistLibraryEndpoints, "writing data for library {type}s"),
        )
        async def return_bool(self) -> bool:
            return True

    @pytest.fixture
    def model(self, api: RemoteAPI) -> HasAPI:
        return self.MockHasAPI(api=api)

    async def test_validate_api_with_valid_api(self, handler: RequestHandler):
        class MockPlaylistEndpoints(PlaylistReadWriteEndpoints, HasLibraryEndpoints[PlaylistLibraryEndpoints]):
            pass

        class MockAPI(RemoteAPI[MockRemoteAuthoriser], HasPlaylistEndpoints[MockPlaylistEndpoints]):
            pass

        model = self.MockHasAPI(api=MockAPI(handler=handler))
        assert await model.return_bool() is True

    async def test_validate_api_fails_on_no_playlist_endpoints(self, handler: RequestHandler):
        class MockAPI(RemoteAPI[MockRemoteAuthoriser], HasTrackEndpoints[MockItemEndpoints]):
            source: ClassVar[str] = "Test"

        model = self.MockHasAPI(api=MockAPI(handler=handler))
        assert await model.return_bool() is False

    async def test_validate_api_fails_on_no_write_library_playlist_endpoints(self, handler: RequestHandler):
        class MockPlaylistEndpoints(PlaylistReadWriteEndpoints, HasLibraryEndpoints[PlaylistBatchReadAllEndpoints]):
            pass

        class MockAPI(RemoteAPI[MockRemoteAuthoriser], HasPlaylistEndpoints[MockPlaylistEndpoints]):
            pass

        model = self.MockHasAPI(api=MockAPI(handler=handler))
        assert await model.return_bool() is False
