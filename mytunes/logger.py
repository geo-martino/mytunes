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
from rich.prompt import Prompt
from termcolor import colored

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

    console: Console = Console()

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

    def print(self, *values, sep=' ', end='\n', header: int | None = None, **kwargs) -> None:
        """
        Wrapper for print. Logs the given ``values`` to the INFO setting.
        If there are no stdout handlers with severity <= INFO, also print this to the terminal.
        This ensures the user sees the ``values`` always.
        """
        message = self.generate_message(sep.join(values), header=header)
        if not values or not self.stdout_handlers or all(h.level > logging.DEBUG for h in self.stdout_handlers):
            self.console.print(*values, sep=sep, end=end, highlight=False, new_line_start=not self.compact)
        elif message:
            self.debug(message, **kwargs)

    def print_line(self, level: int = logging.CRITICAL + 1) -> None:
        """Print a new line only when DEBUG < ``logger level`` <= ``level`` for all console handlers"""
        if not self.compact:
            if self.stdout_handlers and any(logging.DEBUG < h.level <= level for h in self.stdout_handlers):
                self.console.print()

    def input(self, text: str | None = None, choices: list[str] | None = None) -> str:
        """Print dialogue with optional text and get the user's input."""
        if text:
            text = text.strip()
            self.print(text, end="")
            Prompt.prompt_suffix = " "

        inp = Prompt.ask(choices=choices).strip()
        self.debug(f"User input: {inp}")
        return inp

    @staticmethod
    @validate_call
    def generate_message(message: str, header: HeaderType | None = None, hidden: str | None = None) -> str:
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

    @classmethod
    def format_types_to_string(cls, items: Iterable[Any]) -> str:
        """Format the given ``items`` as a string of types for logging."""
        from ._models import ResourceModel
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
        else:
            value_str = values[0]

        return value_str

    def __copy__(self):
        """Do not copy logger"""
        return self

    def __deepcopy__(self, _: dict = None):
        """Do not copy logger"""
        return self


logging.setLoggerClass(Logger)
