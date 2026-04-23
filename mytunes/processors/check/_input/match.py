from collections.abc import Sequence
from typing import ClassVar

from pydantic import Field, InstanceOf
from termcolor import colored

from mytunes import PROGRAM_NAME
from mytunes.core.properties.name import HasName
from mytunes.core.properties.uri import HasMutableURI
from mytunes.processors.check._input.page import _ApiT, InputPage
from mytunes.processors.check._match import BaseInputMatch
from mytunes.result import LogFormatter


class InputMatch[IT: HasMutableURI](BaseInputMatch[_ApiT, IT]):
    _method: ClassVar[str] = "INPUT"

    # WORKAROUND: use `InstanceOf` here to prevent revalidation
    #  which creates a new page hence not preserving current page state
    #  Could alternatively drop the generics, not sure what is best...
    page: InstanceOf[InputPage[_ApiT, IT]] = Field(
        description="The state of the current page"
    )

    @property
    def name(self) -> str:
        if self.page.name is not None:
            return self.page.name

        name = f"{self.page.source} items"
        if self.page.username is not None:
            name = f"{self.page.username}'s {name}"
        return name

    @property
    def _header(self) -> str:
        return "Checking URI matches for {count} items"

    @property
    def _options(self) -> dict[str | None, str]:
        return {
            "<Return/Enter>": "Accept the current match and move on to the next item",
            f"<{self.page.source} URI/URL>": "Assign the given URI to the item",
            "u": f"Mark item as 'Unavailable on {self.page.source}'",
            "n": f"Leave item with no URI. ({PROGRAM_NAME} will still attempt to find this item at the next run)",
            "s": "Skip checking process for all current items",
            "q": "Skip checking process for all current items and quit check",
            None: colored("OR enter a custom URI/URL/ID for this item", "white")
        }

    async def _match_item_with_input(
            self, item: IT, others: Sequence[IT], option: str | None, formatter: LogFormatter
    ) -> str | None:
        name = item.name if isinstance(item, HasName) else str(id(item))
        uri = colored(item.uri, "green") if item.has_uri else colored("NO MATCH", "red")
        text = f"{name} | {uri}"

        while option or (option := self._get_user_input(text, formatter=formatter)):
            match option.casefold():
                case "u":
                    self._set_unavailable_uri(item)
                    break

                case "ua":
                    self._set_unavailable_uri(item)
                    return option

                case "n":
                    self._drop_uri(item)
                    break

                case "na":
                    self._drop_uri(item)
                    return option

                case value if (input_uri := self._create_uri(value, kind=item.type)) is not None:
                    item.uri = input_uri
                    break

                case _:
                    self._log_unrecognised_input(option)

            option = None
