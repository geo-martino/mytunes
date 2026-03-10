from unittest.mock import patch, Mock

import pytest
from aiorequestful.auth import Authoriser
from aiorequestful.request import RequestHandler
from pydantic import ValidationError

from musify.remote.api import RemoteAPI, RemoteAuthoriser, Endpoints
from tests.models.testers import MusifyModelTester


class TestRemoteAPI(MusifyModelTester):
    class MockRemoteAuthoriser(RemoteAuthoriser[Mock]):
        client_id: str = "test_client_id"

        @patch.multiple(
            Authoriser,
            __abstractmethods__=set(),
            authorise=Mock(),
        )
        def create_authoriser(self) -> Authoriser:
            # noinspection PyAbstractClass
            return Authoriser()

    class MockRemoteAPI(RemoteAPI[MockRemoteAuthoriser]):
        tracks: Endpoints
        artists: Endpoints
        albums: Endpoints

    @pytest.fixture
    def model(self) -> RemoteAPI:
        return self.MockRemoteAPI()

    @pytest.fixture
    def authoriser(self) -> RemoteAuthoriser:
        return self.MockRemoteAuthoriser()

    @pytest.fixture
    def handler(self, authoriser: RemoteAuthoriser) -> RequestHandler:
        return RequestHandler.create(authoriser=authoriser.create_authoriser())

    def test_from_handler(self, handler: RequestHandler):
        model = self.MockRemoteAPI.model_validate(handler)
        assert model.tracks._handler is handler
        assert model.artists._handler is handler
        assert model.albums._handler is handler

    def test_from_authoriser(self, authoriser: RemoteAuthoriser):
        model = self.MockRemoteAPI.model_validate(authoriser)
        assert isinstance(model.tracks._handler, RequestHandler)
        assert isinstance(model.artists._handler, RequestHandler)
        assert isinstance(model.albums._handler, RequestHandler)

    def test_from_credentials(self, authoriser: RemoteAuthoriser):
        model = self.MockRemoteAPI.model_validate(authoriser.model_dump())
        assert isinstance(model.tracks._handler, RequestHandler)
        assert isinstance(model.artists._handler, RequestHandler)
        assert isinstance(model.albums._handler, RequestHandler)

    def test_checks_all_handlers_are_the_same(self):
        with pytest.raises(ValidationError, match="All endpoint models must use the same request handler"):
            self.MockRemoteAPI(
                tracks=RequestHandler.create(),
                artists=RequestHandler.create(),
                albums=RequestHandler.create(),
            )
