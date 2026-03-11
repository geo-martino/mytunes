import pytest
from aiorequestful.request import RequestHandler
from pydantic import ValidationError

from musify.models.api import RemoteAPI, RemoteAuthoriser
from tests.models.testers import BaseModelTester
from tests.models.api.utils import MockRemoteAPI, MockRemoteAuthoriser


class TestRemoteAPI(BaseModelTester):
    @pytest.fixture
    def model(self) -> RemoteAPI:
        return MockRemoteAPI()

    @pytest.fixture
    def authoriser(self) -> RemoteAuthoriser:
        return MockRemoteAuthoriser()

    @pytest.fixture
    def handler(self, authoriser: RemoteAuthoriser) -> RequestHandler:
        return RequestHandler.create(authoriser=authoriser.create_authoriser())

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
