import logging
import sys
from collections.abc import Generator
from copy import copy, deepcopy

import pytest
from mytunes.logger import Logger, EXTRA, REPORT, STAT


###########################################################################
## Logger tests
###########################################################################
@pytest.fixture
def logger() -> Generator[Logger]:
    """Yields a :py:class:`Logger` with all handlers removed for testing"""
    logger = Logger(__name__)
    logger.compact = False

    for handler in logger.handlers:
        logger.removeHandler(handler)

    logger.disable_bars = False
    yield logger
    logger.disable_bars = True


def test_additional_levels():
    assert logging.getLevelName("EXTRA") == EXTRA
    assert logging.getLevelName("REPORT") == REPORT
    assert logging.getLevelName("STAT") == STAT

    assert logging.getLoggerClass() == Logger
    assert isinstance(logging.getLogger(__name__), Logger)


def test_file_paths(logger: Logger):
    logger.addHandler(logging.FileHandler(filename="test1.log", delay=True))
    logger.addHandler(logging.FileHandler(filename="test2.log", delay=True))
    assert [path.name for path in logger.file_paths] == ["test1.log", "test2.log"]


def test_copy(logger: Logger):
    assert id(copy(logger)) == id(logger)
    assert id(deepcopy(logger)) == id(logger)


def test_print_line(logger: Logger, capfd: pytest.CaptureFixture):
    logger.setLevel(logging.WARNING)

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
