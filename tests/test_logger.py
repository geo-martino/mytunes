## DEPRECATED?

import logging
import sys
from collections.abc import Generator
from copy import copy, deepcopy

import pytest

from musify.logger import MusifyLogger, INFO_EXTRA, REPORT, STAT

try:
    from tqdm.auto import tqdm
except ImportError:
    tqdm = None


###########################################################################
## MusifyLogger tests
###########################################################################
@pytest.fixture
def logger() -> Generator[MusifyLogger, None, None]:
    """Yields a :py:class:`MusifyLogger` with all handlers removed for testing"""
    logger = MusifyLogger(__name__)
    logger.compact = False

    for handler in logger.handlers:
        logger.removeHandler(handler)

    logger.disable_bars = False
    yield logger
    logger.disable_bars = True


def test_print_line(logger: MusifyLogger, capfd: pytest.CaptureFixture):
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.WARNING)
    logger.addHandler(handler)

    assert logger.stdout_handlers

    logger.print_line(logging.ERROR)  # ERROR is above handler level
    assert capfd.readouterr().out == "\n"

    logger.print_line(logging.WARNING)  # WARNING is at handler level
    assert capfd.readouterr().out == "\n"

    logger.print_line(logging.INFO)  # INFO is below handler level
    assert capfd.readouterr().out == ""

    # compact is True, never print lines
    logger.compact = True

    logger.print_line(logging.ERROR)
    assert capfd.readouterr().out == ""
    logger.print_line(logging.WARNING)
    assert capfd.readouterr().out == ""
    logger.print_line(logging.INFO)
    assert capfd.readouterr().out == ""

    # compact False and handler is at DEBUG level, never print lines
    logger.compact = False
    handler.setLevel(logging.DEBUG)

    logger.print_line(logging.INFO)
    assert capfd.readouterr().out == ""
    logger.print_line(logging.DEBUG)
    assert capfd.readouterr().out == ""
    logger.print_line(0)
    assert capfd.readouterr().out == ""


def test_file_paths(logger: MusifyLogger):
    logger.addHandler(logging.FileHandler(filename="test1.log", delay=True))
    logger.addHandler(logging.FileHandler(filename="test2.log", delay=True))
    assert [path.name for path in logger.file_paths] == ["test1.log", "test2.log"]


@pytest.mark.skipif(tqdm is None, reason="required modules not installed")
def test_tqdm_param_position(logger: MusifyLogger):
    assert not logger._bars
    assert logger._get_tqdm_param_position(2) == 2
    assert logger._get_tqdm_param_position(9) == 9

    # takes next available position when unfinished bars present
    bar = logger.get_synchronous_iterator(iterable=range(0, 50), position=4)
    assert bar.pos == -4
    assert logger._get_tqdm_param_position() == 5
    assert logger._bars

    # clears bars
    for bar in logger._bars:
        bar.n = bar.total
        bar.close()
    assert logger._get_tqdm_param_position() is None
    assert not logger._bars


@pytest.mark.skipif(tqdm is None, reason="required modules not installed")
def test_tqdm_param_leave(logger: MusifyLogger):
    assert logger._get_tqdm_param_leave(position=0)
    assert not logger._get_tqdm_param_leave(position=2)
    assert not logger._get_tqdm_param_leave(position=5)


@pytest.mark.skipif(tqdm is None, reason="required modules not installed")
def test_tqdm_kwargs(logger: MusifyLogger):
    kwargs = dict(iterable=range(0, 50), initial=10, disable=True, file=sys.stderr)
    kwargs_processed = logger._get_tqdm_kwargs(**kwargs)
    assert kwargs_processed["initial"] == 10
    assert kwargs_processed["disable"]

    kwargs = dict(
        iterable=range(0, 50),
        initial=10,
        disable=False,
        file=sys.stderr,
        ncols=500,
        colour="blue",
        smoothing=0.5,
        position=3,
    )

    kwargs_processed = logger._get_tqdm_kwargs(**kwargs)
    assert kwargs_processed["initial"] == 10
    assert not kwargs_processed["disable"]
    assert kwargs_processed["ncols"] != 500
    assert kwargs_processed["colour"] == "blue"
    assert kwargs_processed["smoothing"] != 0.5


@pytest.mark.skipif(tqdm is None, reason="required modules not installed")
def test_tqdm_iterator_synchronous(logger: MusifyLogger):
    logger._bars.clear()

    bar: tqdm = logger.get_synchronous_iterator(
        iterable=range(0, 50), initial=10, disable=True, file=sys.stderr
    )

    assert bar.iterable == range(0, 50)
    assert bar.n == 10
    assert bar.total == 50
    assert bar.leave
    assert bar.disable
    assert bar in logger._bars

    # adheres to disable_bars attribute
    logger.disable_bars = True
    bar = logger.get_synchronous_iterator(
        iterable=range(0, 50),
        initial=10,
        disable=False,
        file=sys.stderr,
        ncols=500,
        colour="blue",
        smoothing=0.5,
        position=3,
    )

    assert not bar.leave
    assert bar.disable
    assert bar.pos == 0

    logger.disable_bars = False


@pytest.mark.skipif(tqdm is None, reason="required modules not installed")
async def test_tqdm_iterator_asynchronous(logger: MusifyLogger):
    async def _task(i: int) -> int:
        return i

    # just check this runs
    tasks = [_task(i) for i in range(10)]
    results = await logger.get_asynchronous_iterator(tasks)

    assert len(results) == len(tasks)
    assert sorted(results) == [i for i in range(len(tasks))]


def test_copy(logger: MusifyLogger):
    assert id(copy(logger)) == id(logger)
    assert id(deepcopy(logger)) == id(logger)


def test_logger_set():
    assert logging.getLevelName("INFO_EXTRA") == INFO_EXTRA
    assert logging.getLevelName("REPORT") == REPORT
    assert logging.getLevelName("STAT") == STAT

    assert logging.getLoggerClass() == MusifyLogger
    assert isinstance(logging.getLogger(__name__), MusifyLogger)
