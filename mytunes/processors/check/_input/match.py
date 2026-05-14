from collections.abc import Sequence
from typing import ClassVar

from pydantic import Field, InstanceOf

from mytunes import PROGRAM_NAME
from mytunes.core.properties.name import HasName
from mytunes.core.properties.uri import HasMutableURI, URI
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
            "q": "Skip checking process for all current items and quit check. No results will be returned.",
            None: "[white]OR enter a custom URI/URL/ID for this item[\\]"
        }

    async def _match_item_with_input(
            self, item: IT, others: Sequence[IT], option: str | None, formatter: LogFormatter
    ) -> str | None:
        name = self._log_match(item, formatter)

        while option or (option := self._get_user_input(name, formatter=formatter)):
            log = option
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

                case _ if (log := self._set_uri(item, value=option)) is None:
                    break

                case _:
                    self._log_unrecognised_input(log)

            option = None

    def _log_match(self, item: IT, formatter: LogFormatter) -> str:
        name = item.name if isinstance(item, HasName) and item.name else str(id(item))
        sep = f" [bold white]|[\\] "

        if item.has_uri and isinstance(uri := item.uri, URI):
            url = f"[blue]{uri.public_url}[\\]"
            uri = f"[green]{uri}[\\]"
            log_parts = [uri, url]
        else:
            log_parts = ["[red]NO MATCH[\\]"]

        self._logger.print(sep.join((formatter.get_value(name), *log_parts)))

        return name
