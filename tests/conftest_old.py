import asyncio
import copy
import logging.config
import shutil
import types
from collections import defaultdict
from pathlib import Path

import pytest
import yaml
from _pytest.fixtures import SubRequest
# noinspection PyProtectedMember
from _pytest.logging import LogCaptureHandler, _remove_ansi_escape_sequences
from aiorequestful.types import UnitCollection

from musify import MODULE_ROOT
from musify._types import Resource
from musify.libraries.remote.spotify.api import SpotifyAPI
from musify.libraries.remote.spotify.wrangle import SpotifyDataWrangler
from musify.logger import MusifyLogger
from musify.utils import to_collection
from tests.libraries.remote.core.utils import ALL_ITEM_TYPES
from tests.libraries.remote.spotify.api.mock import SpotifyMock
from tests.utils import idfn, path_resources


@pytest.fixture(scope="session")
def event_loop():
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# noinspection PyUnusedLocal
@pytest.hookimpl
def pytest_configure(config: pytest.Config):
    """Loads logging config"""
    config_file = path_resources.joinpath("test_logging").with_suffix(".yml")
    if not config_file.is_file():
        return

    with open(config_file, "r", encoding="utf-8") as file:
        log_config = yaml.full_load(file)

    log_config.pop("compact", False)
    MusifyLogger.disable_bars = True
    MusifyLogger.compact = True

    for formatter in log_config["formatters"].values():  # ensure ANSI colour codes in format are recognised
        formatter["format"] = formatter["format"].replace(r"\33", "\33")

    log_config["loggers"][MODULE_ROOT] = log_config["loggers"]["test"]
    logging.config.dictConfig(log_config)


def pytest_collection_modifyitems(items: list[pytest.Function]):
    """Modifies test items in-place, ordering them based on assigned marks."""
    marker_name_order = []  # currently not implemented

    def _get_item_order_index(item: pytest.Function) -> int:
        try:
            name = next(marker.name for marker in item.own_markers if marker.name.casefold() in marker_name_order)
            return marker_name_order.index(name.casefold())
        except (StopIteration, ValueError):
            return len(marker_name_order)

    items.sort(key=_get_item_order_index)


class LogCapturer(LogCaptureHandler):
    """
    Fixture to capture logs regardless of the Propagate flag. See
    https://github.com/pytest-dev/pytest/issues/3697 for details.
    """

    @property
    def text(self) -> str:
        return _remove_ansi_escape_sequences(self.stream.getvalue())

    @property
    def messages(self) -> list[str]:
        return [_remove_ansi_escape_sequences(record.getMessage()) for record in self.records]

    def __init__(self):
        super().__init__()
        self._level: int = logging.INFO
        self._loggers: list[logging.Logger] = []

        self._original_levels: dict[logging.Logger, int] = {}
        self._raw_messages: list[str] = []

    def set_level(self, level: int) -> None:
        """Set the level at which to capture logs"""
        self._level = level

    def add_logger(self, logger: logging.Logger) -> None:
        """Set the logger on which to capture logs"""
        self._loggers.append(logger)

    def emit(self, record: logging.LogRecord) -> None:
        if hasattr(record, "message"):
            self._raw_messages.append(record.message)
        super().emit(record)

    def __call__(self, level: int | None = None, loggers: UnitCollection[logging.Logger] | None = None):
        if level is not None:
            self._level = level
        if loggers is not None:
            self._loggers = to_collection(loggers, list)
        return self

    def __enter__(self):
        self.clear()

        for logger in self._loggers:
            self._original_levels[logger] = logger.level
            logger.setLevel(self._level)
            logger.addHandler(self)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._level = logging.INFO
        self._loggers = []

        for logger, level in self._original_levels.items():
            logger.setLevel(level)
            logger.removeHandler(self)


@pytest.fixture
def log_capturer() -> LogCapturer:
    return LogCapturer()


@pytest.fixture
def path(request: pytest.FixtureRequest | SubRequest, tmp_path: Path) -> Path:
    """
    Copy the path of the source file to the test cache for this test and return the cache path.
    Deletes the test folder when test is done.
    """
    if hasattr(request, "param"):
        src_path = request.param
    else:  # assume path is given at the top-level fixture, get param from this request
        # noinspection PyProtectedMember
        src_path = request._pyfuncitem.callspec.params[request._parent_request.fixturename]

    src_path = Path(src_path)
    trg_path = tmp_path.joinpath(src_path.name)

    trg_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src_path, trg_path)

    yield trg_path

    shutil.rmtree(trg_path.parent)


@pytest.fixture(scope="session", params=ALL_ITEM_TYPES, ids=idfn)
def object_type(request) -> Resource:
    """Yields the valid :py:class:`RemoteObjectTypes` to use throughout tests in this suite as a pytest.fixture."""
    return request.param


@pytest.fixture(scope="session")
def spotify_wrangler():
    """Yields a :py:class:`SpotifyDataWrangler` for testing Spotify data wrangling"""
    return SpotifyDataWrangler()


@pytest.fixture(scope="session")
def spotify_mock() -> SpotifyMock:
    """Yield an authorised and configured :py:class:`SpotifyMock` object"""
    with SpotifyMock() as m:
        yield m


@pytest.fixture(scope="session")
async def spotify_api(spotify_mock: SpotifyMock) -> SpotifyAPI:
    """Yield an authorised :py:class:`SpotifyAPI` object"""
    token = {"access_token": "fake access token", "token_type": "Bearer", "scope": "test-read"}
    # disable any token tests by setting tester as appropriate
    api = SpotifyAPI()
    api.handler.authoriser.response.replace(token)
    api.handler.authoriser.tester.response_test = None
    api.handler.authoriser.tester.max_expiry = 0

    # force no backoff/wait settings
    api.handler.wait_timer = None
    api.handler.retry_timer = None

    async with api as a:
        spotify_mock.reset()
        yield a
