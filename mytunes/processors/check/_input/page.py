from collections.abc import Sequence

from pydantic import field_validator, Field
from termcolor import colored

from mytunes.core.api import RemoteAPI
from mytunes.core.properties.uri import HasURI
from mytunes.processors.check._page import CheckerPage
from mytunes.processors.formatter import ModelFormatter

type _ApiT = RemoteAPI


class InputPage[API: RemoteAPI, CT: HasURI](CheckerPage[_ApiT, CT]):
    name: str | None = Field(
        description="The name for this set of items.",
    )
    items: Sequence[CT] = Field(
        description="The items to be checked on this page."
    )

    item_formatter: ModelFormatter = Field(
        description="The formatter to use for formatting info about the item to print.",
        default=ModelFormatter(
            fields=("Name", "URI", "Public URL"),
            colours=("white", "green", "blue"),
            header=False,
        )
    )

    ###########################################################################
    ## Pause page
    ###########################################################################
    @property
    def _header(self) -> str:
        types = self._logger.format_types_to_string(self.items)
        header = f"These are the matches that exist for all given {types}:"
        header = colored(header, "blue", attrs=["bold"])
        table = self.item_formatter.format(self.items)

        return f"{header}\n\n{table}"

    @property
    def _options(self) -> dict[str, str]:
        return {
            "y/yes": "Accept all the current matches and proceed to the next set of items (if applicable)",
            "n/no": "Reject the current matches and proceed to manually matching each item",
            "q": "Quit check",
        }

    async def pause(self) -> bool:
        """Pause the check process and prompt the user on how to proceed."""
        super().pause()

        while option := self._get_user_input():
            match option.casefold():
                case "y" | "yes":
                    return True

                case "n" | "no":
                    return False

                case _:
                    self._log_unrecognised_input(option)

        return False
