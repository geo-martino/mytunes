import sys
from collections.abc import Iterable, Collection
from contextlib import suppress
from copy import deepcopy

from pydantic import Field, ValidationError
from termcolor import colored

from musify import PROGRAM_NAME
from musify.models.properties.name import HasName
from musify.models.properties.uri import HasURI, URI, HasMutableURI
from musify.models.result import LogFormatter
from musify.processors_new._base import InputProcessor
from musify.processors_new.check._exception import SkipPage, QuitImmediately
from musify.processors_new.check._match._base import CheckerMatch
from musify.processors_new.check.result import CheckResult
from musify.processors_new.formatter import ModelFormatter


class InputMatch(CheckerMatch, InputProcessor):
    formatter: ModelFormatter = Field(
        description="The formatter to use for formatting info about the item to print.",
        default=ModelFormatter(
            fields=("Name", "Artist", "Album", "Length", "Released At"),
            colours=("white", "blue", "blue", "red", "yellow"),
            header=True,
        )
    )

    async def match[CT: HasURI](self, items: Collection[CT], uri: URI, name: str) -> CheckResult[CT]:
        """Match the given items that have missing URIs with user input."""
        missing = self.get_missing_items(items)
        if not missing:
            message = "No items with mutable URIs to match to input, skipping match"
            self._log_debug("SKIP", name, message)
            return CheckResult()

        help_text = self._format_help_text_for_match_with_input(name=name, count=len(missing))
        self.logger.print_message("\n" + help_text)

        self._log_debug("INPUT", name, f"Getting user input for {len(missing)} items")

        initial = deepcopy(missing)
        formatter = self._configure_formatter_for_items(missing)
        option = None

        with suppress(SkipPage):
            for item in missing:
                option = await self._match_item_with_input(item, uri=uri, formatter=formatter, option=option)

        return self._compare_uri_changes(initial=initial, changes=missing)

    def _format_help_text_for_match_with_input(self, name: str | None = None, count: int | None = None) -> str:
        header = None
        if name is not None:
            message = "The following {items} were removed and/or matches were not found."
            message = message.format(items="items" if count is None else f"{count} items")

            header = colored(name, "blue", attrs=["bold"]) + ": "
            header += colored(message, "red")

        options = {
            f"<{self.page.source} URI/URL>": "Assign the given URI to the item",
            "u": f"Mark item as 'Unavailable on {self.page.source}'",
            "ua": "Same as 'u' option but apply to all items in this playlist in addition to this item",
            "n": f"Leave item with no URI. ({PROGRAM_NAME} will still attempt to find this item at the next run)",
            "na": "Same as 'n' option but apply to all items in this playlist in addition to this item",
            "r": "Recheck playlist for all items in the collection",
            "p": "Print all info for the current item",
            "s": "Skip checking process for all current playlists",
            "q": "Skip checking process for all current playlists and quit check",
            "h": "Show this dialogue again",
        }

        help_text = self._format_help_text(options=options, header=header)
        help_text += "\nOR enter a custom URI/URL/ID for this item"

        return help_text + "\n"

    async def _match_item_with_input[CT: HasMutableURI](
            self, item: CT, uri: URI, formatter: LogFormatter, option: str | None = None
    ) -> str | None:
        name = item.name if isinstance(item, HasName) else str(id(item))
        request_input = option is None

        while True:
            if option is None:
                option = self._get_user_input(name, formatter=formatter)

            match option.casefold():
                case "h":
                    help_text = self._format_help_text_for_match_with_input()
                    self.logger.print_message("\n" + help_text)

                case "s":
                    raise SkipPage()

                case "q":
                    raise QuitImmediately()

                case "p":
                    info = self.formatter.format(item)
                    self.logger.print_message(info)

                case "u":
                    item.uri = self._create_uri(None, kind=item.type)
                    break

                case "ua":
                    item.uri = self._create_uri(None, kind=item.type)
                    return option

                case "n":
                    del item.uri
                    break

                case "na":
                    del item.uri
                    return option

                case "r":
                    await self.page.refresh_playlist_items(uri)
                    if self._match_item_with_playlist(item, uri):
                        break

                case "ra":
                    if request_input:  # only refresh on the first loop
                        await self.page.refresh_playlist_items(uri)
                    if self._match_item_with_playlist(item, uri):
                        return option

                case value if (input_uri := self._create_uri(value, kind=item.type)) is not None:
                    item.uri = input_uri
                    break

                case _:
                    self.logger.warning(
                        f"Invalid URI/URL/ID for {self.page.source}, please try again or enter 'h' for options"
                    )

            option = None

    def _create_uri(self, value: str | None, kind: str) -> URI | None:
        with suppress(ValidationError):
            return self.page.api.create_uri(value=value, kind=kind)
        return None

    def _match_item_with_playlist(self, item: HasMutableURI, uri: URI) -> bool:
        items = self.page.get_stored_playlist_items(uri)

        # don't match with items that have already been matched
        matched = self.get_valid_items(self.page.get_collection_items(uri))
        items = [it for it in items if it not in matched]

        match = self._match_item_with_others(item, items, "INPUT")
        if match is not None:
            return True

        name = self.page.get_playlist_name(uri)
        self.logger.warning(f"No match found for this item in the playlist: {name!r}")
        return False

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
    def _compare_uri_changes[CT: HasURI](initial: Iterable[CT], changes: Iterable[CT]) -> CheckResult[CT]:
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