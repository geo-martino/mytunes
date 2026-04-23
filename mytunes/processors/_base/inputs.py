import textwrap
from abc import abstractmethod
from collections.abc import Sequence
from typing import ClassVar

from pydantic import Field
from rich.progress import TaskID
from tabulate import tabulate
from termcolor import colored

from mytunes.core.properties.logger import HasLogger, HasProgress
from mytunes.core.properties.order import Position
from mytunes.processors._base import Processor
from mytunes.processors._flow import SkipPage, QuitImmediately
from mytunes.result import LogFormatter


class InputProcessor(Processor, HasLogger):
    """
    Processor that gets user input as part of it processing.

    Contains methods for getting user input and printing formatted options text to the terminal.
    """
    input_formatter: ClassVar[LogFormatter] = LogFormatter(
        colour="yellow", colour_attributes=["bold"]
    )

    def _get_user_input(
            self, text: str = "Enter input", formatter: LogFormatter | None = None, choices: list[str] | None = None
    ) -> str:
        """Print dialogue with optional text and get the user's input."""
        if formatter is None:
            formatter = self.input_formatter

        log = f"{formatter.get_value(text)} {colored("|", "white", attrs=["bold"])}"
        return self._logger.input(log, choices=choices)


# noinspection PyAbstractClass
class OptionsProcessor(InputProcessor):
    @property
    def _header(self) -> str | None:
        """The header to display in the help text of the processor."""
        return ""

    @property
    @abstractmethod
    def _options(self) -> dict[str | None, str]:
        """The options to display in the help text of the processor."""
        return {
            "h": "Show this dialogue again",
        }

    def _print_help_text(self, header: str | bool = True) -> None:
        """Format help text with a given mapping of options. Add an option header to include before options."""
        options = self._options | OptionsProcessor._options.fget(self)

        width = self._logger.console.width
        # +2 for ':' and space between cols in tabulate
        max_key_width = max(len(key) for key in options if key) + 2

        rows = []
        for key, description in options.items():
            if key is None:  # Used only for printing additional text after options
                continue

            row = (
                colored(key, "blue", attrs=["bold"]) + ":",
                colored("\n".join(textwrap.wrap(description, width - max_key_width)), "white"),
            )
            rows.append(row)

        if header is True and self._header:
            header = self._header

        header = f"{header}\n\n" if header else ""
        sub_header = colored("Enter one of the following", "cyan") + ":\n"
        log = header + sub_header + tabulate(
            rows,
            tablefmt="plain",
            colalign=("left", "left"),
        )
        if additional_text := options.get(None):
            log += f"\n{additional_text}"

        self._logger.print(log)
        self._logger.print_line()

    def _get_user_input(
            self, text: str = "Enter input", formatter: LogFormatter | None = None, choices: list[str] | None = None
    ) -> str:
        option = super()._get_user_input(text=text, formatter=formatter, choices=choices)

        # we can process common options here and just request for input again
        if self._process_common_options(option):
            return self._get_user_input(text=text, formatter=formatter)

        return option

    def _process_common_options(self, option: str) -> bool:
        """
        Process common options for this processor.
        Boolean return value indicates whether the option was handled.
        Control flow exceptions raised always need to be handled by child classes if supported.
        """
        match option:
            case "h":
                self._print_help_text(header=False)
                return True

            case "s" if "s" in self._options:
                raise SkipPage()

            case "q" if "q" in self._options:
                raise QuitImmediately()

        return False

    def _log_unrecognised_input(self, value: str | Sequence[str], help_key: str = "h") -> None:
        if isinstance(value, str):
            value = [value]

        for val in value:
            message = f"Unrecognised input: {val!r}. Enter {help_key!r} for valid options."
            self._logger.warning(colored(message, "red"))


class PageProcessor(OptionsProcessor, HasProgress):
    """Processor that runs in pages, getting user input and printing formatted options text to the terminal."""
    position: Position | None = Field(
        description="The current position of this page in the process.",
        default=None
    )
    task_id: TaskID | None = Field(
        description=(
            "The task ID for the progress bar to use to display. If None, a progress bar will not be displayed."
        ),
        default=None,
    )

    @abstractmethod
    def pause(self) -> None:
        """Pause the process and prompt the user for input to proceed."""
        self._print_help_text(header=True)

    def _get_user_input(
            self, text: str | None = None, formatter: LogFormatter | None = None, choices: list[str] | None = None
    ) -> str | None:
        if text is None:  # change the default text
            text = "Enter"
        if self.position is not None:
            text += f" ({self.position})"

        return super()._get_user_input(text=text, formatter=formatter, choices=choices)
