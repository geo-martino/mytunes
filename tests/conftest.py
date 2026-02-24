import logging
from collections import defaultdict
from collections.abc import Collection
from copy import copy
from io import BytesIO
from pathlib import Path
from random import choice, sample
from types import MethodType

import mutagen.id3
import pytest
from PIL import Image, ImageFile as PILImageFile
# noinspection PyProtectedMember
from _pytest.logging import LogCaptureHandler, _remove_ansi_escape_sequences
from aioresponses import aioresponses, CallbackResult
from faker import Faker

# noinspection PyProtectedMember
from musify._types import to_list
from musify.models.properties.image import ImageURL, ImageFile


@pytest.fixture(scope="session")
def faker() -> Faker:
    """Sets up and yields a basic Faker object for fake data"""
    return Faker()


@pytest.fixture(scope="session")
def mock_response():
    with aioresponses() as m:
        yield m


@pytest.fixture
def image_bytes(faker: Faker) -> list[bytes]:
    return [
        faker.image(
            size=(faker.random_int(100, 300), faker.random_int(100, 300)),
            image_format=choice(["jpeg", "png"])
        )
        for _ in range(faker.random_int(3, 5))
    ]


@pytest.fixture
def image_objects(image_bytes: list[bytes]) -> list[PILImageFile.ImageFile]:
    return list(map(Image.open, map(BytesIO, image_bytes)))


@pytest.fixture
def image_types(image_bytes: list[bytes]) -> set[str]:
    """Fixture to provide a valid image type."""
    types = {
        name for name, enum in vars(mutagen.id3.PictureType).items()
        if isinstance(enum, mutagen.id3.PictureType)
    }
    return set(sample(list(types), len(image_bytes)))


@pytest.fixture
def image_files(image_types: set[str], faker: Faker, tmp_path: Path) -> list[Path]:
    """Fixture to provide a list of image files."""
    image_files = []

    for _ in range(faker.random_int(3, 5)):
        size = (faker.random_int(100, 300), faker.random_int(100, 300))
        image_bytes = faker.image(size=size, image_format=choice(["jpeg", "png"]))

        path = tmp_path.joinpath(faker.file_name(category="image"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(image_bytes)
        img = Image.open(BytesIO(image_bytes))

        image_file = ImageFile(
            path=path,
            type=choice(list(image_types)),
            mime=img.get_format_mimetype(),
            height=img.height,
            width=img.width
        )
        image_files.append(image_file)

    return image_files


@pytest.fixture
def image_urls(image_types: set[str], faker: Faker, mock_response: aioresponses) -> list[ImageURL]:
    image_urls: list[ImageURL] = []

    for _ in range(faker.random_int(3, 5)):
        size = (faker.random_int(100, 300), faker.random_int(100, 300))
        image_bytes = faker.image(size=size, image_format=choice(["jpeg", "png"]))
        img = Image.open(BytesIO(image_bytes))
        url = faker.url()

        mock_response.get(url, repeat=True, callback=lambda *_, **__: CallbackResult(method="GET", body=image_bytes),)
        image_url = ImageURL(
            url=url,
            type=choice(list(image_types)),
            mime=img.get_format_mimetype(),
            height=img.height,
            width=img.width
        )
        image_urls.append(image_url)

    return image_urls


# This is a fork of the pytest-lazy-fixture package
# Fixes applied for issues with pytest >8.0: https://github.com/TvoroG/pytest-lazy-fixture/issues/65
# noinspection PyProtectedMember
@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    if hasattr(item, "_request"):
        item._request._fillfixtures = MethodType(
            fillfixtures(item._request._fillfixtures), item._request
        )


def fillfixtures(_fillfixtures):
    # noinspection PyProtectedMember
    def fill(request):
        item = request._pyfuncitem
        fixturenames = getattr(item, "fixturenames", None)
        if fixturenames is None:
            fixturenames = request.fixturenames

        if hasattr(item, "callspec"):
            for param, val in sorted_by_dependency(item.callspec.params, fixturenames):
                if val is not None and is_lazy_fixture(val):
                    item.callspec.params[param] = request.getfixturevalue(val.name)
                elif param not in item.funcargs:
                    item.funcargs[param] = request.getfixturevalue(param)

        _fillfixtures()
    return fill


# noinspection PyUnusedLocal
@pytest.hookimpl(tryfirst=True)
def pytest_fixture_setup(fixturedef, request):
    val = getattr(request, "param", None)
    if is_lazy_fixture(val):
        request.param = request.getfixturevalue(val.name)


# noinspection PyProtectedMember
def pytest_runtest_call(item):
    if hasattr(item, "funcargs"):
        for arg, val in item.funcargs.items():
            if is_lazy_fixture(val):
                item.funcargs[arg] = item._request.getfixturevalue(val.name)


# noinspection PyUnusedLocal
@pytest.hookimpl(hookwrapper=True)
def pytest_pycollect_makeitem(collector, name, obj):
    # noinspection PyGlobalUndefined
    global current_node
    current_node = collector
    yield
    current_node = None


# noinspection PyUnusedLocal
def pytest_make_parametrize_id(config, val, argname):
    if is_lazy_fixture(val):
        return val.name


@pytest.hookimpl(hookwrapper=True)
def pytest_generate_tests(metafunc):
    yield

    normalize_metafunc_calls(metafunc)


# noinspection PyProtectedMember
def normalize_metafunc_calls(metafunc, used_keys=None):
    newcalls = []
    for callspec in metafunc._calls:
        calls = normalize_call(callspec, metafunc, used_keys)
        newcalls.extend(calls)
    metafunc._calls = newcalls


# noinspection PyProtectedMember
def copy_metafunc(metafunc):
    copied = copy(metafunc)
    copied.fixturenames = copy(metafunc.fixturenames)
    copied._calls = []

    try:
        copied._ids = copy(metafunc._ids)
    except AttributeError:
        # pytest>=5.3.0
        pass

    copied._arg2fixturedefs = copy(metafunc._arg2fixturedefs)
    return copied


# noinspection PyProtectedMember
def normalize_call(callspec, metafunc, used_keys):
    fm = metafunc.config.pluginmanager.get_plugin("funcmanage")

    used_keys = used_keys or set()
    keys = set(callspec.params.keys()) - used_keys

    for arg in keys:
        val = callspec.params[arg]
        if is_lazy_fixture(val):
            try:
                if pytest.version_tuple >= (8, 0, 0):
                    fixturenames_closure, arg2fixturedefs = fm.getfixtureclosure(
                        metafunc.definition.parent, [val.name], {}
                    )
                else:
                    _, fixturenames_closure, arg2fixturedefs = fm.getfixtureclosure(
                        [val.name], metafunc.definition.parent
                    )

            except ValueError:
                # 3.6.0 <= pytest < 3.7.0; `FixtureManager.getfixtureclosure` returns 2 values
                fixturenames_closure, arg2fixturedefs = fm.getfixtureclosure([val.name], metafunc.definition.parent)
            except AttributeError:
                # pytest < 3.6.0; `Metafunc` has no `definition` attribute
                fixturenames_closure, arg2fixturedefs = fm.getfixtureclosure([val.name], current_node)

            extra_fixturenames = [fname for fname in fixturenames_closure if fname not in callspec.params]

            newmetafunc = copy_metafunc(metafunc)
            newmetafunc.fixturenames = extra_fixturenames
            newmetafunc._arg2fixturedefs.update(arg2fixturedefs)
            newmetafunc._calls = [callspec]
            fm.pytest_generate_tests(newmetafunc)

            normalize_metafunc_calls(newmetafunc, used_keys | {arg})
            return newmetafunc._calls

        used_keys.add(arg)
    return [callspec]


def sorted_by_dependency(params, fixturenames):
    free_fm = []
    non_free_fm = defaultdict(list)

    for key in _sorted_argnames(params, fixturenames):
        val = params.get(key)

        if key not in params or not is_lazy_fixture(val) or val.name not in params:
            free_fm.append(key)
        else:
            non_free_fm[val.name].append(key)

    non_free_fm_list = []
    for free_key in free_fm:
        non_free_fm_list.extend(
            _tree_to_list(non_free_fm, free_key)
        )

    return [(key, params.get(key)) for key in (free_fm + non_free_fm_list)]


def _sorted_argnames(params, fixturenames):
    argnames = set(params.keys())

    for name in fixturenames:
        if name in argnames:
            argnames.remove(name)
        yield name

    if argnames:
        for name in argnames:
            yield name


def _tree_to_list(trees, leave):
    lst = []
    for ls in trees[leave]:
        lst.append(ls)
        lst.extend(
            _tree_to_list(trees, ls)
        )
    return lst


def lazy_fixture(names):
    if isinstance(names, str):
        return LazyFixture(names)
    else:
        return [LazyFixture(name) for name in names]


pytest.lazy_fixture = lazy_fixture


def is_lazy_fixture(val):
    return isinstance(val, LazyFixture)


class LazyFixture(object):
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return '<{} "{}">'.format(self.__class__.__name__, self.name)

    def __eq__(self, other):
        return self.name == other.name


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

    def __call__(self, level: int | None = None, loggers: logging.Logger | Collection[logging.Logger] | None = None):
        if level is not None:
            self._level = level
        if loggers is not None:
            self._loggers = to_list(loggers)
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
