## DEPRECATED?

"""
All classes and operations relating to the logger objects used throughout the entire package.
"""
import asyncio
import logging
import logging.config
import logging.handlers
import os
import sys
from asyncio import Future
from collections.abc import Iterable, Awaitable
from pathlib import Path
from typing import Any, Annotated

from pydantic import Field, validate_call
from termcolor import colored

try:
    from tqdm.auto import tqdm
except ImportError:
    tqdm = None

type ProgressBarType[T] = Iterable[T] | tqdm if tqdm is not None else Iterable[T]
type HeaderType = Annotated[int, Field(ge=1, le=4)]

EXTRA = logging.INFO - 1
logging.addLevelName(EXTRA, "EXTRA")
logging.EXTRA = EXTRA

REPORT = logging.INFO - 3
logging.addLevelName(REPORT, "REPORT")
logging.REPORT = REPORT

STAT = logging.DEBUG + 3
logging.addLevelName(STAT, "STAT")
logging.STAT = STAT


class Logger(logging.Logger):
    """The logger for all logging operations."""

    #: When true, never print a new line in the console when :py:meth:`print()` is called
    compact: bool = False
    #: When true, all bars returned by :py:meth:`get_progress_bar()` will be disabled by default
    disable_bars: bool = False
    #: All currently active progress bars
    _bars: list[tqdm] = []

    @property
    def file_paths(self) -> list[Path]:
        """Get a list of the paths of all file handlers for this logger"""
        def extract_paths(lggr: logging.Logger) -> None:
            """Extract file path from the handlers of the given ``lggr``"""
            for handler in lggr.handlers:
                if isinstance(handler, logging.FileHandler) and handler.baseFilename not in paths:
                    paths.append(Path(handler.baseFilename))

        paths = []
        logger = self
        extract_paths(logger)
        while logger.propagate and logger.parent:
            logger = logger.parent
            extract_paths(logger)
        return paths

    @property
    def stdout_handlers(self) -> set[logging.StreamHandler]:
        """Get a list of all :py:class:`logging.StreamHandler` handlers that log to stdout"""
        console_handlers = set()
        for handler in self.handlers + list(logging.getHandlerNames()):
            if isinstance(handler, str):
                handler = logging.getHandlerByName(handler)
            if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
                console_handlers.add(handler)

        return console_handlers
    
    @validate_call
    def debug(self, msg: str, *args, header: HeaderType | None = None, hidden: str | None = None, **kwargs) -> None:
        msg = self.generate_message(msg, header, hidden)
        super().debug(msg, *args, **kwargs)

    def stat(self, msg: str, *args, header: HeaderType | None = None, hidden: str | None = None, **kwargs) -> None:
        """Log 'msg % args' with severity 'STAT'."""
        if self.isEnabledFor(STAT):
            msg = self.generate_message(msg, header, hidden)
            self._log(STAT, msg, args, **kwargs)

    def report(self, msg: str, *args, header: HeaderType | None = None, hidden: str | None = None, **kwargs) -> None:
        """Log 'msg % args' with severity 'REPORT'."""
        if self.isEnabledFor(REPORT):
            msg = self.generate_message(msg, header, hidden)
            self._log(REPORT, msg, args, **kwargs)

    @validate_call
    def extra(
            self, msg: str, *args, header: HeaderType | None = None, hidden: str | None = None, **kwargs
    ) -> None:
        """Log 'msg % args' with severity 'EXTRA'."""
        if self.isEnabledFor(EXTRA):
            msg = self.generate_message(msg, header, hidden)
            self._log(EXTRA, msg, args, **kwargs)
    
    @validate_call
    def info(self, msg: str, *args, header: HeaderType | None = None, hidden: str | None = None, **kwargs) -> None:
        msg = self.generate_message(msg, header, hidden)
        super().info(msg, *args, **kwargs)
    
    @validate_call
    def warning(self, msg: str, *args, header: HeaderType | None = None, hidden: str | None = None, **kwargs) -> None:
        msg = self.generate_message(msg, header, hidden)
        super().warning(msg, *args, **kwargs)
    
    @validate_call
    def error(self, msg: str, *args, header: HeaderType | None = None, hidden: str | None = None, **kwargs) -> None:
        msg = self.generate_message(msg, header, hidden)
        super().error(msg, *args, **kwargs)
    
    @validate_call
    def critical(self, msg: str, *args, header: HeaderType | None = None, hidden: str | None = None, **kwargs) -> None:
        msg = self.generate_message(msg, header, hidden)
        super().critical(msg, *args, **kwargs)

    def print_line(self, level: int = logging.CRITICAL + 1) -> None:
        """Print a new line only when DEBUG < ``logger level`` <= ``level`` for all console handlers"""
        if not self.compact:
            if self.stdout_handlers and any(logging.DEBUG < h.level <= level for h in self.stdout_handlers):
                print()

    def print_message(self, *values, sep=' ', end='\n', **kwargs) -> None:
        """
        Wrapper for print. Logs the given ``values`` to the INFO setting.
        If there are no stdout handlers with severity <= INFO, also print this to the terminal.
        This ensures the user sees the ``values`` always.
        """
        message = sep.join(values)
        if message:
            self.info(message, **kwargs)

        if not values or not self.stdout_handlers or all(h.level > logging.INFO for h in self.stdout_handlers):
            print(*values, sep=sep, end=end)

    @staticmethod
    @validate_call
    def generate_message(
            message: str,
            header: Annotated[int, Field(ge=1, le=4)] | None = None,
            hidden: str | None = None
    ) -> str:
        match header:
            case None:
                header = ""
            case 1:
                header = "->"
            case 2:
                header = " >"
            case 3:
                header = " -"
            case 4:
                header = " ·"

        if header:
            header = colored(header, "magenta", attrs=["bold"])
            message = colored(message, "white", attrs=["bold"])

        if hidden:
            hidden = colored(hidden, "dark_grey", attrs=["dark"])

        parts = [header, message, hidden]
        return " ".join(part for part in parts if part).strip()

    @staticmethod
    def format_list_to_string(values: Iterable[Any]) -> str:
        """Format the given ``values`` as a list of strings for logging."""
        values = list(map(str, values))
        value_str = ", ".join(values[:-1])
        if value_str:
            value_str = " & ".join([value_str, values[-1]])
        else:
            value_str = values[0]

        return value_str

    def get_synchronous_iterator[T: Any](
            self, iterable: Iterable[T] | None = None, total: T | int | None = None, **kwargs
    ) -> ProgressBarType[T]:
        """
        Return an appropriately configured tqdm progress bar if installed.
        If not, return either the given ``iterable`` if given or simply ``range(total)``.
        For tqdm kwargs, see :py:class:`tqdm`
        """
        if tqdm is None:
            return iter(iterable) if iterable is not None else range(total)

        bar = tqdm(iterable=iterable, **self._get_tqdm_kwargs(total=total, **kwargs))
        self._bars.append(bar)
        return bar

    def get_asynchronous_iterator[T](
            self, tasks: Iterable[Awaitable[T]], **kwargs
    ) -> Awaitable[list[T]] | Future[list[T]]:
        """
        Return an appropriately configured asynchronous tqdm progress bar if installed.
        If not, gather the given awaitable objects from ``tasks`` and return a coroutine.

        Note that tqdm does not preserve the order of the input awaitables and will return results in a random order.
        For tqdm kwargs, see :py:class:`tqdm`
        """
        if tqdm is None:
            return asyncio.gather(*tasks)
        return tqdm.gather(*tasks, **self._get_tqdm_kwargs(**kwargs))

    def _get_tqdm_kwargs(self, **kwargs) -> dict[str, Any]:
        preset_keys = ("leave", "disable", "file", "ncols", "colour", "smoothing")

        try:
            cols = os.get_terminal_size().columns
        except OSError:
            cols = 120

        # adjust kwargs to defaults if needed
        kwargs["position"] = self._get_tqdm_param_position(**kwargs)
        return dict(
            leave=self._get_tqdm_param_leave(**kwargs),
            disable=self.disable_bars or kwargs.get("disable", False),
            file=sys.stdout,
            ncols=cols,
            colour=kwargs.get("colour", "blue"),
            smoothing=0.1,
            **{k: v for k, v in kwargs.items() if k not in preset_keys}
        )

    def _get_tqdm_param_position(self, position: int = None, **__) -> int | None:
        if position is not None:
            return position

        # clear closed bars
        self._bars = [bar for bar in self._bars if bar.n < (bar.total or 0)]
        if self._bars:
            return abs(min(bar.pos for bar in self._bars)) + 1

    def _get_tqdm_param_leave(self, position: int | None, leave: bool = None, **__) -> bool:
        if leave is not None:
            return leave

        return all([
            bool(self.stdout_handlers) or (h.level > logging.DEBUG for h in self.stdout_handlers),
            position is None or position == 0
        ])

    def __copy__(self):
        """Do not copy logger"""
        return self

    def __deepcopy__(self, _: dict = None):
        """Do not copy logger"""
        return self


logging.setLoggerClass(Logger)
