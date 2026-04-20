"""
All classes and operations relating to the logger objects used throughout the entire package.
"""
import logging
import logging.config
import logging.handlers
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Annotated

from pydantic import Field, validate_call
from rich.console import Console
from rich.highlighter import NullHighlighter
from rich.logging import RichHandler
from rich.prompt import Prompt
from termcolor import colored

type HeaderType = Annotated[int, Field(ge=1, le=4)]

EXTRA = logging.INFO - 1
logging.addLevelName(EXTRA, "EXTRA")
logging.EXTRA = EXTRA

REPORT = logging.INFO - 3
logging.addLevelName(REPORT, "REPORT")
logging.REPORT = REPORT

STAT = logging.INFO - 5
logging.addLevelName(STAT, "STAT")
logging.STAT = STAT

# WORKAROUND: Needed to ensure ANSI codes log as expected by default
RichHandler.HIGHLIGHTER_CLASS = NullHighlighter


class Logger(logging.Logger):
    """The logger for all logging operations."""

    #: When true, never print a new line in the console when :py:meth:`print()` is called
    compact: bool = False

    console: Console = Console(highlight=False, highlighter=NullHighlighter())

    @property
    def stdout_handlers(self) -> list[logging.Handler]:
        """Get a list of all handlers used by this logger that log to stdout."""
        handlers = []
        for handler in self.get_all_handlers():
            match handler:
                case logging.StreamHandler() if handler not in handlers and handler.stream == sys.stdout:
                    handlers.append(handler)
                case RichHandler() if handler not in handlers:
                    handlers.append(handler)

        return handlers

    @property
    def file_handlers(self) -> list[logging.FileHandler]:
        """Get a list of all handlers used by this logger that log to a file."""
        handlers = []
        for handler in self.get_all_handlers():
            match handler:
                case logging.FileHandler() if handler not in handlers:
                    handlers.append(handler)

        return handlers

    @property
    def file_paths(self) -> list[Path]:
        """Get a list of the paths of all file handlers for this logger"""
        paths = []
        for handler in self.file_handlers:
            if handler.baseFilename not in paths:
                paths.append(Path(handler.baseFilename))
        return paths

    def get_all_handlers(self, logger: logging.Logger = None) -> list[logging.Handler]:
        """Get all handlers for this logger, including from any parent loggers if propagate is set to True."""
        if logger is None:
            logger = self

        handlers = logger.handlers.copy()
        if not logger.propagate or logger.parent is None:
            return handlers

        for handler in self.get_all_handlers(logger.parent):
            if handler not in handlers:
                handlers.append(handler)

        return handlers

    def _will_log_to_stdout(self, level: int) -> bool:
        return level >= self.getEffectiveLevel() and any(level >= h.level for h in self.stdout_handlers)

    def _log(
            self,
            level: int,
            msg: object,
            args: logging._ArgsType = (),
            header: HeaderType | None = None,
            hidden: str | None = None,
            new_line_start: bool = False,
            new_line_end: bool = False,
            **kwargs,
    ):
        if not self.compact and new_line_start:
            self.print_line(level)

        msg = self.generate_message(msg, header, hidden)
        super()._log(level, msg, args, **kwargs)

        if not self.compact and new_line_end:
            self.print_line(level)

    # need to override each func to ensure args actually get passed to _log as expected
    def debug(self, *args, **kwargs) -> None:
        if self.isEnabledFor(logging.DEBUG):
            self._log(logging.DEBUG, *args, **kwargs)

    def stat(self, *args, **kwargs) -> None:
        """Log 'msg % args' with severity 'STAT'."""
        if self.isEnabledFor(STAT):
            self._log(STAT, *args, **kwargs)

    def report(self, *args, **kwargs) -> None:
        """Log 'msg % args' with severity 'REPORT'."""
        if self.isEnabledFor(REPORT):
            self._log(REPORT, *args, **kwargs)

    def extra(self, *args, **kwargs) -> None:
        """Log 'msg % args' with severity 'EXTRA'."""
        if not self.isEnabledFor(EXTRA):
            self._log(EXTRA, *args, **kwargs)

    def info(self, *args, **kwargs) -> None:
        if self.isEnabledFor(logging.INFO):
            self._log(logging.INFO, *args, **kwargs)

    def warning(self, *args, **kwargs) -> None:
        if self.isEnabledFor(logging.WARNING):
            self._log(logging.WARNING, *args, **kwargs)

    def error(self, *args, **kwargs) -> None:
        if self.isEnabledFor(logging.ERROR):
            self._log(logging.ERROR, *args, **kwargs)

    def critical(self, *args, **kwargs) -> None:
        if self.isEnabledFor(logging.CRITICAL):
            self._log(logging.CRITICAL, *args, **kwargs)

    def print(self, *values, sep=' ', header: int | None = None, **kwargs) -> None:
        """
        Wrapper for print. Logs the given ``values`` to the INFO setting.
        If there are no stdout handlers with severity <= INFO, also print this to the terminal.
        This ensures the user sees the ``values`` always.
        """
        message = self.generate_message(sep.join(values), header=header)
        if not values or not self._will_log_to_stdout(logging.DEBUG):
            self.console.print(message, sep=sep, new_line_start=not self.compact, **kwargs)
        elif message:
            self.debug(message)

    def print_line(self, level: int = logging.CRITICAL + 1) -> None:
        """Print a new line only when DEBUG < ``logger level`` <= ``level`` for all console handlers"""
        if self.compact or not self.stdout_handlers:
            return

        if self._will_log_to_stdout(level):
            self.console.print()

    def input(self, text: str | None = None, choices: list[str] | None = None) -> str:
        """Print dialogue with optional text and get the user's input."""
        if text:
            text = text.strip()

        Prompt.prompt_suffix = " "
        inp = Prompt.ask(text, choices=choices, default="" if choices else ..., show_default=False).strip()
        self.debug(f"User input: {inp}")
        return inp

    @staticmethod
    @validate_call
    def generate_message(message: object, header: HeaderType | None = None, hidden: str | None = None) -> str:
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
        return " ".join(map(str, (part for part in parts if part))).strip()

    @classmethod
    def format_types_to_string(cls, items: Iterable[Any]) -> str:
        """Format the given ``items`` as a string of types for logging."""
        from ._base.resource import ResourceModel
        types = {f"{it.type.rstrip("s")}s" for it in items if isinstance(it, ResourceModel)}
        return cls.format_list_to_string(types)

    @staticmethod
    def format_list_to_string(values: Iterable[Any]) -> str:
        """Format the given ``values`` as a list of strings for logging."""
        if isinstance(values, set):
            values = sorted(values)

        values = list(map(str, values))
        value_str = ", ".join(values[:-1])
        if value_str:
            value_str = " & ".join([value_str, values[-1]])
        elif values:
            value_str = values[0]

        return value_str

    def __copy__(self):
        """Do not copy logger"""
        return self

    def __deepcopy__(self, _: dict = None):
        """Do not copy logger"""
        return self


logging.setLoggerClass(Logger)
