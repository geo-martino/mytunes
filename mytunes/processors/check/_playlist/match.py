import sys
from collections import Counter
from collections.abc import MutableSequence, Collection, Iterable
from contextlib import suppress
from copy import copy
from copy import deepcopy
from typing import ClassVar

from pydantic import Field, ValidationError
from pydantic import InstanceOf
from termcolor import colored

from mytunes import PROGRAM_NAME
from mytunes.core.properties.name import HasName
from mytunes.core.properties.uri import HasImmutableURI
from mytunes.core.properties.uri import HasURI, HasMutableURI
from mytunes.core.properties.uri import URI
from mytunes.core.sequence import UniqueSequence
from mytunes.processors._flow import SkipPage
from mytunes.processors.check._playlist.page import PlaylistsPage, _ApiT
from mytunes.processors.check.result import CheckResult
from mytunes.processors.formatter import ModelFormatter
from mytunes.processors.match import Matcher
from mytunes.result import LogFormatter
from mytunes.processors.check._match import CheckerMatch
from ..._base.inputs import OptionsProcessor


# noinspection PyAbstractClass
class _BaseMatch[IT: HasMutableURI](CheckerMatch[_ApiT, IT], HasImmutableURI):
    type: ClassVar[str] = "playlist"

    # WORKAROUND: use `InstanceOf` here to prevent revalidation
    #  which creates a new page hence not preserving current page state
    #  Could alternatively drop the generics, not sure what is best...
    page: InstanceOf[PlaylistsPage[_ApiT, IT]] = Field(
        description="The state of the current page"
    )
    matcher: Matcher = Field(
        description=(
            "The matcher to use for confirming closest matches returned by the API "
            "when comparing changes in playlists."
        ),
    )

    @property
    def name(self) -> str:
        """The name of the related playlist."""
        return self.page.get_playlist_name(self.uri)

    def _match_item_with_others[OT: HasURI](self, item: IT, others: Collection[OT]) -> OT | None:
        if not isinstance(item, HasMutableURI):
            return

        match = self.matcher.match(item, others)
        if match is None or not match.has_uri:
            return

        messages = [f"Updating {item.type} URI", f"{item.uri} -> {match.uri}"]
        self._log_debug(messages, item=item, pad="<")
        item.uri = match.uri

        return match


class PlaylistMatch[IT: HasMutableURI](_BaseMatch[IT]):
    _method: ClassVar[str] = "PLAYLIST"

    async def match(self, items: Collection[IT]) -> CheckResult[IT]:
        """Match the given that have missing URIs with items in the current playlist."""
        self._logger.info(f"Checking for changes to items in {self.page.source} playlist: {self.name}", header=2)

        current = await self.page.get_current_playlist_items(self.uri)
        added, removed, unchanged, unavailable, missing = self._compare_items(items=items, others=current)

        if not added and not removed and not missing:
            message = "Playlist unchanged and no missing URIs, skipping match"
            self._log_skip(message)
            return CheckResult(unchanged=unchanged, unavailable=unavailable, skipped=missing)

        missing += removed
        for item in missing:
            if isinstance(item, HasMutableURI):
                del item.uri

        if not missing:
            message = "No items changed in playlist and no items with missing matches, skipping match"
            self._log_skip(message)
            return CheckResult(unchanged=unchanged, unavailable=unavailable)

        if not added:
            message = "No items added, skipping match"
            self._log_skip(message)
            return CheckResult(unchanged=unchanged, unavailable=unavailable, skipped=missing)

        if not any(isinstance(item, HasMutableURI) for item in missing):
            message = "No items with mutable URIs to match with added items, skipping match"
            self._log_skip(message)
            return CheckResult(unchanged=unchanged, unavailable=unavailable, skipped=missing)

        changed = self._match_items_with_others(items=missing, others=added)
        return CheckResult(changed=changed, unchanged=unchanged, unavailable=unavailable, skipped=missing)

    def _compare_items[RT: HasURI](
            self, items: Collection[IT], others: Collection[RT]
    ) -> tuple[list[RT], list[IT], list[IT], list[IT], list[IT]]:
        valid_items = self.get_valid_items(items)
        items_unique = UniqueSequence(valid_items)
        others_unique = UniqueSequence(others)

        added = list(others_unique.difference(items_unique))
        removed = list(items_unique.difference(others_unique))
        removed += self._compare_duplicate_items(valid_items, others, removed)
        unchanged = list(items_unique.intersection(others_unique))
        unavailable = self.get_unavailable_items(items)
        missing = self.get_missing_items(items)

        if self.page.use_existing_playlists and (initial := len(self.page.get_initial_playlist_items(self.uri))) > 0:
            initial_message = "items that were in the playlist before starting"
            self._log_debug(initial_message, count=initial)

        self._log_debug("items at start", count=len(items))
        self._log_debug("items that are confirmed as unavailable", count=len(unavailable))
        self._log_debug("items added", count=len(added))
        self._log_debug("items removed", count=len(removed))
        self._log_debug("difference", count=len(added) - len(removed))
        self._log_debug("items unchanged", count=len(unchanged))
        self._log_debug("items still with missing URI", count=len(missing))
        self._log_debug("total item changes", count=len(added) - len(removed))

        return added, removed, unchanged, unavailable, missing

    @staticmethod
    def _compare_duplicate_items(initial: Collection[IT], others: Iterable[HasURI], unique: list[IT]) -> list[IT]:
        # if item collection originally contained duplicate URIS and one or more of the duplicates were removed
        # find removed duplicate items by looking for changes in counts
        initial_counts = Counter(item.uri for item in initial)
        other_counts = Counter(item.uri for item in others)
        current_counts = Counter(item.uri for item in unique)

        duplicates = []
        for item in initial:
            initial_count = initial_counts.get(item.uri, 0)
            other_count = other_counts.get(item.uri, 0)
            current_count = current_counts.get(item.uri, 0)

            if initial_count == 1 or initial_count <= current_count + other_count:
                continue

            duplicates.append(item)
            current_counts = Counter(item.uri for item in unique + duplicates)  # refresh counts

        return duplicates

    def _match_items_with_others(self, items: MutableSequence[IT], others: MutableSequence[HasURI]) -> list[IT]:
        initial = len(items)
        changed = []

        for item in copy(items):  # copy to safely modify items while iterating
            if not others:
                break

            match = self._match_item_with_others(item, others)
            if match is None:
                continue

            changed.append(item)
            items.remove(item)
            others.remove(match)

        final = len(items)
        self._log_debug("items switched", count=initial - final)
        self._log_debug("items still not found", count=final)

        return changed


class InputMatch[IT: HasMutableURI](_BaseMatch[IT], OptionsProcessor):
    _method: ClassVar[str] = "INPUT"

    item_formatter: ModelFormatter = Field(
        description="The formatter to use for formatting info about the item to print.",
        default=ModelFormatter(
            fields=("Name", "Artist", "Album", "Length", "Released At"),
            colours=("white", "blue", "blue", "red", "yellow"),
            header=True,
        )
    )

    async def match(self, items: Collection[IT]) -> CheckResult[IT]:
        """Match the given items that have missing URIs with user input."""
        missing = self.get_missing_items(items)
        if not missing:
            message = "No items with mutable URIs to match to input, skipping match"
            self._log_skip(message)
            return CheckResult()

        self._log_debug(f"Getting user input for {len(missing)} items")
        self._print_help_text(header=self._get_header(len(missing)))

        initial = deepcopy(missing)
        formatter = self._configure_formatter_for_items(missing)
        option = None

        with suppress(SkipPage):  # suppress so we can still compare changes and return a result
            for item in missing:
                option = await self._match_item_with_input(item, others=items, option=option, formatter=formatter)

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
    def _get_header(self, count: int) -> str:
        message = f"The following {count} items were removed and/or matches were not found."
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
            self, item: IT, others: Collection[IT], option: str | None, formatter: LogFormatter
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
                    if self._match_item_with_playlist(item, others=others):
                        break

                case "ra":
                    if input_requested:  # only refresh on the first loop
                        await self.page.refresh_playlist_items(self.uri)
                    if self._match_item_with_playlist(item, others=others):
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
        self._log_debug(messages, item=item, pad="<")

    def _drop_uri(self, item: IT) -> None:
        del item.uri
        self._log_debug(f"Marking {item.type} as missing", item=item, pad="<")

    def _create_uri(self, value: str | None, kind: str) -> URI | None:
        with suppress(ValidationError):
            return self.page.api.create_uri(value=value, kind=kind)
        return None

    def _match_item_with_playlist(self, item: IT, others: Collection[IT]) -> bool:
        items = self.page.get_stored_playlist_items(self.uri)

        # don't match with items that have already been matched
        matched = self.get_valid_items(others)
        unmatched = [it for it in items if it not in matched]

        match = self._match_item_with_others(item, unmatched)
        if match is not None:
            return True

        message = f"No match found for this item in the playlist: {self.name!r}"
        self._logger.warning(colored(message, "red"))
        return False
