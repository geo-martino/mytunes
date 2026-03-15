from typing import ClassVar

import pytest
from aiorequestful.request import RequestHandler
from pydantic import ValidationError

from musify.models.api import RemoteAPI, RemoteAuthoriser, HasSavedEndpoints, HasAPI
from musify.models.api.playlist import HasPlaylistEndpoints, PlaylistReadWriteEndpoints, \
    PlaylistReadWriteSavedEndpoints, PlaylistReadSavedEndpoints
from musify.models.api.track import HasTrackEndpoints
from tests.models.api.utils import MockRemoteAPI, MockRemoteAuthoriser, MockTrackEndpoints
from tests.models.testers import BaseModelTester


@pytest.fixture
def authoriser() -> RemoteAuthoriser:
    return MockRemoteAuthoriser()


@pytest.fixture
def handler(authoriser: RemoteAuthoriser) -> RequestHandler:
    return RequestHandler.create(authoriser=authoriser.create_authoriser())


@pytest.fixture
def api() -> RemoteAPI:
    return MockRemoteAPI()


class TestRemoteAPI(BaseModelTester):
    @pytest.fixture
    def model(self, api: RemoteAPI) -> RemoteAPI:
        return api

    def test_from_handler(self, handler: RequestHandler):
        model = MockRemoteAPI.model_validate(handler)
        assert model.users._handler is handler
        assert model.tracks._handler is handler
        assert model.artists._handler is handler
        assert model.albums._handler is handler
        assert model.playlists._handler is handler

    def test_from_authoriser(self, authoriser: RemoteAuthoriser):
        model = MockRemoteAPI.model_validate(authoriser)
        assert isinstance(model.users._handler, RequestHandler)
        assert isinstance(model.tracks._handler, RequestHandler)
        assert isinstance(model.artists._handler, RequestHandler)
        assert isinstance(model.albums._handler, RequestHandler)
        assert isinstance(model.playlists._handler, RequestHandler)

    def test_from_credentials(self, authoriser: RemoteAuthoriser):
        model = MockRemoteAPI.model_validate(authoriser.model_dump())
        assert isinstance(model.users._handler, RequestHandler)
        assert isinstance(model.tracks._handler, RequestHandler)
        assert isinstance(model.artists._handler, RequestHandler)
        assert isinstance(model.albums._handler, RequestHandler)
        assert isinstance(model.playlists._handler, RequestHandler)

    def test_checks_all_handlers_are_the_same(self):
        with pytest.raises(ValidationError, match="All endpoint models must use the same request handler"):
            MockRemoteAPI(
                users=RequestHandler.create(),
                tracks=RequestHandler.create(),
                artists=RequestHandler.create(),
                albums=RequestHandler.create(),
                playlists=RequestHandler.create(),
            )


class TestHasAPI(BaseModelTester):
    class MockHasAPI(HasAPI):
        source: ClassVar[str] = "test"

        @HasAPI._validate_api(
            "playlist",
            False,
            (None, HasPlaylistEndpoints, "{type} endpoints"),
            ("playlists", PlaylistReadWriteEndpoints, "writing data for {type}s"),
            ("playlists", HasSavedEndpoints, "saved {type}s endpoints"),
            ("playlists.saved", PlaylistReadWriteSavedEndpoints, "writing data for saved {type}s"),
        )
        def return_bool(self) -> bool:
            return True

    @pytest.fixture
    def model(self, api: RemoteAPI) -> HasAPI:
        return self.MockHasAPI(api=api)

    def test_validate_api_with_valid_api(self, handler: RequestHandler):
        class MockPlaylistEndpoints(PlaylistReadWriteEndpoints, HasSavedEndpoints[PlaylistReadWriteSavedEndpoints]):
            pass

        class MockAPI(RemoteAPI[MockRemoteAuthoriser], HasPlaylistEndpoints[MockPlaylistEndpoints]):
            pass

        model = self.MockHasAPI(api=MockAPI(handler=handler))
        assert model.return_bool() is True

    def test_validate_api_fails_on_no_playlist_endpoints(self, handler: RequestHandler):
        class MockAPI(RemoteAPI[MockRemoteAuthoriser], HasTrackEndpoints[MockTrackEndpoints]):
            pass

        model = self.MockHasAPI(api=MockAPI(handler=handler))
        assert model.return_bool() is False

    def test_validate_api_fails_on_no_write_saved_playlist_endpoints(self, handler: RequestHandler):
        class MockPlaylistEndpoints(PlaylistReadWriteEndpoints, HasSavedEndpoints[PlaylistReadSavedEndpoints]):
            pass

        class MockAPI(RemoteAPI[MockRemoteAuthoriser], HasPlaylistEndpoints[MockPlaylistEndpoints]):
            pass

        model = self.MockHasAPI(api=MockAPI(handler=handler))
        assert model.return_bool() is False
