import sys
from collections.abc import Iterable
from contextlib import suppress
from copy import deepcopy

from pydantic import Field, ValidationError
from termcolor import colored

from mytunes import PROGRAM_NAME
from mytunes.processors._flow import SkipPage
from mytunes.processors.check._match._base import CheckerMatch
from mytunes.processors.check.result import CheckResult
from mytunes.processors.formatter import ModelFormatter
from mytunes.properties.name import HasName
from mytunes.properties.uri import URI, HasMutableURI
from mytunes.result import LogFormatter
from ..._base.inputs import OptionsProcessor


class InputMatch[IT: HasMutableURI](CheckerMatch[IT], OptionsProcessor):
    item_formatter: ModelFormatter = Field(
        description="The formatter to use for formatting info about the item to print.",
        default=ModelFormatter(
            fields=("Name", "Artist", "Album", "Length", "Released At"),
            colours=("white", "blue", "blue", "red", "yellow"),
            header=True,
        )
    )

    async def match(self) -> CheckResult[IT]:
        """Match the given items that have missing URIs with user input."""
        missing = self.missing_items
        if not missing:
            message = "No items with mutable URIs to match to input, skipping match"
            self._log_debug("SKIP", message)
            return CheckResult()

        self._log_debug("INPUT", f"Getting user input for {len(missing)} items")
        self._print_help_text(with_header=True)

        initial = deepcopy(missing)
        formatter = self._configure_formatter_for_items(missing)
        option = None

        with suppress(SkipPage):  # suppress so we can still compare changes and return a result
            for item in missing:
                option = await self._match_item_with_input(item, formatter=formatter, option=option)

        return self._compare_uri_changes(initial=initial, changes=missing)

    @classmethod
    def _configure_formatter_for_items(cls, items: Iterable) -> LogFormatter:
        width = min(
            max(len(item.name) if isinstance(item, HasName) else 0 for item in items),
            cls.input_formatter.max_width or sys.maxsize,
        )
        kwargs = vars(cls.input_formatter)
        kwargs.pop("width", None)

        return cls.input_formatter.__class__(**kwargs, width=width or None)

    @staticmethod
    def _compare_uri_changes(initial: Iterable[IT], changes: Iterable[IT]) -> CheckResult[IT]:
        changed = []
        unchanged = []
        unavailable = []
        skipped = []

        for init, change in zip(initial, changes, strict=True):
            if init.has_uri is not False and change.has_uri is False:
                unavailable.append(change)
            elif init.has_uri is None and change.has_uri is None:
                skipped.append(change)
            elif init.uri == change.uri:
                unchanged.append(change)
            else:
                changed.append(change)

        return CheckResult(changed=changed, unchanged=unchanged, unavailable=unavailable, skipped=skipped)

    ###########################################################################
    ## Pause page
    ###########################################################################
    @property
    def _header(self) -> str:
        message = f"The following {len(self.missing_items)} items were removed and/or matches were not found."
        name = colored(self.name, "blue", attrs=["bold"])
        return f"{name}: {message}"

    @property
    def _options(self) -> dict[str | None, str]:
        return {
            "p": "Print more info about the current item",
            f"<{self.page.source} URI/URL>": "Assign the given URI to the item",
            "u": f"Mark item as 'Unavailable on {self.page.source}'",
            "ua": "Same as 'u' option but apply to all items in this playlist in addition to this item",
            "n": f"Leave item with no URI. ({PROGRAM_NAME} will still attempt to find this item at the next run)",
            "na": "Same as 'n' option but apply to all items in this playlist in addition to this item",
            "r": "Recheck playlist for all items in the collection",
            "ra": (
                "Same as 'r' option but also check for all other items in this playlist. "
                "If a match for an item cannot be found, stop and prompt the user again."
            ),
            "s": "Skip checking process for all current playlists",
            "q": "Skip checking process for all current playlists and quit check",
            None: colored("OR enter a custom URI/URL/ID for this item", "white")
        }

    async def _match_item_with_input(
            self, item: IT, formatter: LogFormatter, option: str | None = None
    ) -> str | None:
        name = item.name if isinstance(item, HasName) else str(id(item))
        input_requested = option is None

        while option or (option := self._get_user_input(name, formatter=formatter)):
            match option.casefold():
                case "p":
                    info = self.item_formatter.format(item)
                    self._logger.print(info)

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

                case "r":
                    await self.page.refresh_playlist_items(self.uri)
                    if self._match_item_with_playlist(item):
                        break

                case "ra":
                    if input_requested:  # only refresh on the first loop
                        await self.page.refresh_playlist_items(self.uri)
                    if self._match_item_with_playlist(item):
                        return option

                case value if (input_uri := self._create_uri(value, kind=item.type)) is not None:
                    # set uri from input
                    item.uri = input_uri
                    break

                case _:
                    self._log_unrecognised_input(option)

            option = None

    def _set_unavailable_uri(self, item: IT) -> None:
        item.uri = self._create_uri(None, kind=item.type)
        messages = [f"Marking {item.type} as unavailable", f"URI={item.uri}"]
        self._log_debug("INPUT", item=item, messages=messages, pad="<")

    def _drop_uri(self, item: IT) -> None:
        del item.uri
        self._log_debug("INPUT", item=item, messages=f"Marking {item.type} as missing", pad="<")

    def _create_uri(self, value: str | None, kind: str) -> URI | None:
        with suppress(ValidationError):
            return self.page.api.create_uri(value=value, kind=kind)
        return None

    def _match_item_with_playlist(self, item: IT) -> bool:
        items = self.page.get_stored_playlist_items(self.uri)

        # don't match with items that have already been matched
        matched = self.valid_items
        items = [it for it in items if it not in matched]

        match = self._match_item_with_others(item, items, "INPUT")
        if match is not None:
            return True

        message = f"No match found for this item in the playlist: {self.name!r}"
        self._logger.warning(colored(message, "red"))
        return False
