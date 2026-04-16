import sys

import pytest
from faker import Faker

SYSTEM_PLATFORM_MAP = {
    "win32": "windows",
    "darwin": "mac",
    "linux": "linux",
}


@pytest.fixture
def platform() -> str:
    return SYSTEM_PLATFORM_MAP[sys.platform]


@pytest.fixture
def system_paths(faker: Faker) -> dict[str, str]:
    return {
        "windows": faker.file_path(file_system_rule="windows"),
        "mac": faker.file_path(file_system_rule="linux"),
        "linux": faker.file_path(file_system_rule="linux"),
    }
