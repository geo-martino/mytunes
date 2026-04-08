import asyncio
import logging
from collections.abc import Iterable, Callable, Generator, Coroutine, Awaitable, AsyncGenerator
from contextlib import AbstractAsyncContextManager, AbstractContextManager
from functools import cached_property
from typing import Self, ClassVar, Any

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn, \
    TimeRemainingColumn, TaskID

from musify.logger import Logger
from .._base import BaseModel


class HasLogger(BaseModel):
    """Represents a resource that has a logger."""

    @cached_property
    def _logger(self) -> Logger:
        return logging.getLogger(__name__)


class HasProgress(BaseModel, AbstractContextManager, AbstractAsyncContextManager):
    """Represents a resource that has a progress bar logger."""
    _progress: ClassVar[Progress] = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}: "),
        BarColumn(bar_width=None),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        "/",
        TimeRemainingColumn(compact=True),
        console=Logger.console,
    )

    def __enter__(self) -> Self:
        super().__enter__()
        if not self._progress.live.is_started:
            self._progress.__enter__()
        return self

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        self.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._progress.__exit__(exc_type, exc_val, exc_tb)
        return super().__exit__(exc_type, exc_val, exc_tb)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.__exit__(exc_type, exc_val, exc_tb)
        return await super().__aexit__(exc_type, exc_val, exc_tb)

    def _run_tasks[T](
            self,
            tasks: Iterable[Callable[[], T]],
            task_id: TaskID | None = None,
            predicate: Callable[[T], bool] | None = None,
            remove: bool = True,
    ) -> list[T]:
        """
        Synchronously run the given tasks with progress output if a task_id is provided.
        Largely just a wrapper to turn :py:meth:`.wrap_tasks` into a callable task to get the results.

        :param tasks: The tasks to run.
        :param task_id: The progress bar task ID to run the tasks for. If not given, no progress bar will be shown.
        :param predicate: Only return the task result if the result adheres to this predicate.
            When None, doesn't return the result if None.
        :param remove: Whether to remove the progress bar task when done.
        :return: The results of the tasks.
        """
        tasks = self._wrap_tasks(tasks, task_id, predicate)
        print("TASKS", tasks)
        result = [it for it in tasks]

        if remove and task_id in self._progress.task_ids:
            self._progress.remove_task(task_id)
        return result

    def _wrap_tasks[T](
            self,
            tasks: Iterable[Callable[[], T]],
            task_id: TaskID | None = None,
            predicate: Callable[[T], bool] | None = None,
    ) -> Generator[T]:
        for task in tasks:
            print(task)
            result = task()
            if task_id is not None and task_id in self._progress.task_ids:
                self._progress.advance(task_id, advance=1)

            if callable(predicate) and predicate(result):
                yield result
            elif predicate is None and result is not None:
                yield result

    async def _run_tasks_async[T](
            self,
            tasks: Iterable[Coroutine[Any, Any, T]],
            task_id: TaskID | None = None,
            predicate: Callable[[T], bool] | None = None,
            remove: bool = True,
    ) -> list[T]:
        """
        Asynchronously run the given tasks with progress output if a task_id is provided.
        Largely just a wrapper to turn :py:meth:`.wrap_tasks_async` into an awaitable task to get the results.

        :param tasks: The tasks to run.
        :param task_id: The progress bar task ID to run the tasks for. If not given, no progress bar will be shown.
        :param predicate: Only return the task result if the result adheres to this predicate.
            When None, doesn't return the result if None.
        :param remove: Whether to remove the progress bar task when done.
        :return: The results of the tasks.
        """
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(task) for task in tasks]
            tasks = self._wrap_tasks_async(tasks, task_id, predicate)
            result = [it async for it in tasks]

        if remove and task_id in self._progress.task_ids:
            self._progress.remove_task(task_id)
        return result

    async def _wrap_tasks_async[T](
            self,
            tasks: Iterable[Awaitable[T]],
            task_id: TaskID | None = None,
            predicate: Callable[[T], bool] | None = None,
    ) -> AsyncGenerator[T]:
        for task in tasks:
            result = await task
            if task_id is not None and task_id in self._progress.task_ids:
                self._progress.advance(task_id, advance=1)

            if callable(predicate) and predicate(result):
                yield result
            elif predicate is None and result is not None:
                yield result
