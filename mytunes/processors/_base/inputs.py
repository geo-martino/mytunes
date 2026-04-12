import textwrap
from abc import abstractmethod
from typing import ClassVar

from pydantic import Field
from rich.progress import TaskID
from tabulate import tabulate
from termcolor import colored

from mytunes.processors._base import Processor
from mytunes.processors._flow import SkipPage, QuitImmediately
from ..._models.properties.logger import HasLogger, HasProgress
from ..._models.properties.order import Position
from ..._models.result import LogFormatter


# noinspection PyAbstractClass
class InputProcessor(Processor, HasLogger):
    """
    Processor that gets user input as part of it processing.

    Contains methods for getting user input and printing formatted options text to the terminal.
    """
    input_formatter: ClassVar[LogFormatter] = LogFormatter(
        colour="yellow", colour_attributes=["bold"]
    )

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

    def _print_help_text(self, with_header: bool = True) -> None:
        """Format help text with a given mapping of options. Add an option header to include before options."""
        options = self._options | InputProcessor._options.fget(self)

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

        header = f"{self._header}\n\n" if with_header and self._header else ""
        sub_header = colored("Enter one of the following", "cyan") + ":\n"
        log = header + sub_header + tabulate(
            rows,
            tablefmt="plain",
            colalign=("left", "left"),
        )
        if additional_text := options.get(None):
            log += f"\n{additional_text}"

        self._logger.print(log + "\n")

    def _get_user_input(self, text: str = "Enter input", formatter: LogFormatter | None = None) -> str:
        """Print dialogue with optional text and get the user's input."""
        if formatter is None:
            formatter = self.input_formatter

        log = f"{formatter.get_value(text)} {colored("|", "white", attrs=["bold"])}"
        option = self._logger.input(log)

        self._logger.debug(f"User input: {option}")

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
                self._print_help_text(with_header=False)
                return True

            case "s" if "s" in self._options:
                raise SkipPage()

            case "q" if "q" in self._options:
                raise QuitImmediately()

        return False

    def _log_unrecognised_input(self, text: str, help_key: str = "h") -> None:
        message = f"Unrecognised input: {text!r}. Enter {help_key!r} for valid options."
        self._logger.warning(colored(message, "red"))


class PageProcessor(InputProcessor, HasProgress):
    """Processor that runs in pages, getting user input and printing formatted options text to the terminal."""
    position: Position = Field(
        description="The current position of this page in the process."
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
        self._progress.stop()
        self._print_help_text(with_header=True)

    def _get_user_input(self, text: str | None = None, formatter: LogFormatter | None = None) -> str | None:
        if text is None:  # change the default text
            text = f"Enter ({self.position})"
        return super()._get_user_input(text=text, formatter=formatter)
