"""
Base classes for all processors in this module. Also contains decorators for use in implementations.
"""
import os
import textwrap
from collections.abc import Mapping, Iterable
from typing import Any, ClassVar

from tabulate import tabulate
from termcolor import colored

from musify.models import BaseModel
from musify.models.properties.logger import HasLogger
from musify.models.properties.name import HasName
from musify.models.properties.uri import HasURI
from musify.models.result import LogFormatter


class Processor(BaseModel):
    """Generic base class for processors"""
    @classmethod
    def _format_item_message(
            cls,
            method: str,
            item: Any,
            messages: str | Iterable,
            pad: str = " ",
    ) -> str:
        if isinstance(messages, str):
            messages = (messages,)

        title = cls._get_item_log_value(item)
        header = f"{pad[0] * 3} {method.upper():<7}: {title}"
        return "|" + " | ".join([header] + list(map(str, messages)))

    @staticmethod
    def _get_item_log_value(item: Any) -> str:
        match item:
            case str() as value:
                return value
            case HasURI() as it if it.has_uri:
                return str(it.uri)
            case HasName() as it:
                return str(it.name)
            case _:
                return "- UNKNOWN -"


class InputProcessor(Processor, HasLogger):
    """
    Processor that gets user input as part of it processing.

    Contains methods for getting user input and printing formatted options text to the terminal.
    """
    input_formatter: ClassVar[LogFormatter] = LogFormatter(
        colour="yellow", colour_attributes=["bold"]
    )

    def _get_user_input(self, text: str | None = None, formatter: LogFormatter | None = None) -> str:
        """Print dialogue with optional text and get the user's input."""
        if not text:
            text = "Enter input"

        if formatter is None:
            formatter = self.input_formatter

        log = f"{formatter.get_value(text)} {colored("|", "white", attrs=["bold"])}"
        inp = input(log + " ").strip()

        self.logger.debug(f"User input: {inp}")
        return inp

    def _log_unrecognised_input(self, text: str, help_key: str = "h") -> None:
        message = f"Unrecognised input: {text!r}. Enter {help_key!r} for valid options."
        self.logger.warning(colored(message, "red"))

    @staticmethod
    def _format_help_text(options: Mapping[str, str], header: str | None = None) -> str:
        """Format help text with a given mapping of options. Add an option header to include before options."""
        try:
            cols = os.get_terminal_size().columns
        except OSError:
            cols = 120

        max_key_width = max(len(key) for key in options)

        rows = []
        for key, description in options.items():
            row = (
                colored(key, "blue", attrs=["bold"]) + (":" if description else ""),
                colored("\n".join(textwrap.wrap(description, cols - max_key_width)), "white"),
            )
            rows.append(row)

        header = "\n".join(textwrap.wrap(header, cols)) + "\n\n" if header else ""
        sub_header = colored("Enter one of the following", "cyan") + ":\n"
        log = header + sub_header + tabulate(
            rows,
            tablefmt="plain",
            colalign=("left", "left"),
        )

        return log
