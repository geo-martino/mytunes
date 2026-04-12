import sys

import pytest

SYSTEM_PLATFORM_MAP = {
    "win32": "windows",
    "darwin": "mac",
    "linux": "linux",
}


@pytest.fixture
def platform() -> str:
    return SYSTEM_PLATFORM_MAP[sys.platform]
