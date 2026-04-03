import logging
import sys
from collections.abc import Generator
from copy import copy, deepcopy
from functools import partial

import pytest

from musify.logger import Logger, EXTRA, REPORT, STAT


###########################################################################
## Logger tests
###########################################################################
@pytest.fixture
def logger() -> Generator[Logger, None, None]:
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


def test_run_tasks_sync_gets_results(logger: Logger):
    tasks = [partial(lambda x: x, i) for i in range(10)]
    task_id = logger.progress.add_task("Test", total=len(tasks))

    results = logger.run_tasks(tasks, task_id=task_id, remove=False)

    assert task_id in logger.progress.task_ids
    assert next(task for task in logger.progress.tasks if task.id == task_id).completed
    assert len(results) == len(tasks)
    assert sorted(results) == [i for i in range(len(tasks))]


def test_run_tasks_sync_removes_task(logger: Logger):
    tasks = [partial(lambda x: x, i) for i in range(10)]
    task_id = logger.progress.add_task("Test", total=len(tasks))

    logger.run_tasks(tasks, task_id=task_id, remove=True)
    assert task_id not in logger.progress.task_ids


def test_run_tasks_sync_runs_without_task_id(logger: Logger):
    tasks = [partial(lambda x: x, i) for i in range(10)]

    results = logger.run_tasks(tasks)

    assert len(results) == len(tasks)
    assert sorted(results) == [i for i in range(len(tasks))]


async def test_run_tasks_async_gets_results(logger: Logger):
    async def _task(i: int) -> int:
        return i

    tasks = [_task(i) for i in range(10)]
    task_id = logger.progress.add_task("Test", total=len(tasks))

    results = await logger.run_tasks_async(tasks, task_id=task_id, remove=False)

    assert task_id in logger.progress.task_ids
    assert next(task for task in logger.progress.tasks if task.id == task_id).completed
    assert len(results) == len(tasks)
    assert sorted(results) == [i for i in range(len(tasks))]


async def test_run_tasks_async_removes_task(logger: Logger):
    async def _task(i: int) -> int:
        return i

    tasks = [_task(i) for i in range(10)]
    task_id = logger.progress.add_task("Test", total=len(tasks))

    await logger.run_tasks_async(tasks, task_id=task_id, remove=True)
    assert task_id not in logger.progress.task_ids


async def test_run_tasks_async_runs_without_task_id(logger: Logger):
    async def _task(i: int) -> int:
        return i

    tasks = [_task(i) for i in range(10)]

    results = await logger.run_tasks_async(tasks)

    assert len(results) == len(tasks)
    assert sorted(results) == [i for i in range(len(tasks))]
