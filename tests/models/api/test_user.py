from unittest.mock import Mock

import pytest
from aiorequestful.request import RequestHandler
from faker import Faker

from musify.models.api.user import UserEndpoints
from musify.models.user import RemoteUser
from tests.models.api.testers import EndpointsTester
from tests.models.api.utils import MockUserEndpoints
from tests.utils import SimpleURI


class TestUserEndpoints(EndpointsTester):
    @pytest.fixture
    def model(self, handler: RequestHandler) -> UserEndpoints:
        return MockUserEndpoints(handler=handler)

    @pytest.fixture
    def user(self, faker: Faker) -> RemoteUser:
        return RemoteUser(
            name=faker.name(), uri=SimpleURI.create_random(RemoteUser.type))

    async def test_context_sets_user(self, model: UserEndpoints, user: RemoteUser, mock_get: Mock):
        assert model.user is None
        mock_get.return_value = user

        async with model:
            assert model.user is user

        assert model.user is user  # doesn't reset after context exit
        mock_get.assert_called_once()
