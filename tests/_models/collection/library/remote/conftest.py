from collections.abc import Generator
from unittest.mock import Mock, patch

import pytest

from mytunes._models.api import BatchReadAllEndpoints


@pytest.fixture
def mock_get_all() -> Generator[Mock, None, None]:
    with patch.object(BatchReadAllEndpoints, "get_all") as mock_get_all:
        yield mock_get_all
