from collections.abc import Generator
from unittest.mock import Mock, patch, AsyncMock

import pytest
from aiorequestful.auth import Authoriser
from mytunes.core.api import BatchReadAllEndpoints, RemoteAPI
from mytunes.core.api.user import UserEndpoints
from remote import MockRemoteAPI


@pytest.fixture
def mock_get_all() -> Generator[Mock]:
    with patch.object(BatchReadAllEndpoints, "get_all") as mock_get_all:
        yield mock_get_all


@pytest.fixture
def api() -> Generator[RemoteAPI]:
    with (
        patch.object(Authoriser, "authorise", new_callable=AsyncMock),
        patch.object(UserEndpoints, "get_me", return_value=None, new_callable=AsyncMock)
    ):
        yield MockRemoteAPI()
