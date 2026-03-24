from collections.abc import Generator
from unittest.mock import Mock, patch

import pytest

from musify.models.api import ReadSavedEndpoints


@pytest.fixture
def mock_get_all() -> Generator[Mock, None, None]:
    with patch.object(ReadSavedEndpoints, "get_all") as mock_get_all:
        yield mock_get_all
