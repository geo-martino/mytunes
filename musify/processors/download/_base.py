"""
Processor that helps user download songs from collections based on given configuration.
"""
import itertools
import math
from collections.abc import Iterable, Collection, Sequence, Iterator
from webbrowser import open as webopen

from pydantic import Field, validate_call, PositiveInt, \
    conlist, AliasChoices
from termcolor import colored
from yarl import URL

from musify._types import StrippedString
from musify.models import ResourceModel
from musify.models.collection import CollectionModel
from musify.models.properties.order import Position
from musify.processors._base import InputProcessor
from musify.processors.download.stores import AudioStore


class StoreManager(InputProcessor):
    """Runs operations for helping the user to download items."""

    stores: conlist(AudioStore.annotation, min_length=1) = Field(
        description="The stores to open searches on.",
        validation_alias=AliasChoices("sites", "urls"),
    )
    fields: Sequence[StrippedString] = Field(
        description="The fields to take from an item for use as the query string when opening sites.",
    )
    interval: PositiveInt = Field(
        description="The number of tracks to open sites for before pausing for user input.",
        default=1,
    )
    unique_only: bool = Field(
        description=(
            "Only open sites for items with unique queries. If false, sites will be opened for all items "
            "regardless of whether their query is the same as another item or not."
        ),
        default=True,
    )

    @validate_call
    def open_sites_for_collections(self, collections: Sequence[CollectionModel]) -> None:
        """Run the download helper for all tracks in the given ``collections``."""
        items = tuple(itertools.chain.from_iterable(coll.items for coll in collections))
        return self.open_sites_for_items(items=items)

    @validate_call
    def open_sites_for_items[T: ResourceModel](self, items: Sequence[T] | CollectionModel[T]) -> None:
        """
        Run the download helper for the given ``items``.

        Opens the formatted ``urls`` for each item in all items in the user's browser.
        """
        if isinstance(items, CollectionModel):
            items = list(items.items)

        self._log_start(items, fields=self.fields)
        item_urls = self._format_urls_for_items(items, fields=self.fields)

        total = len(item_urls)
        page_total = math.ceil(total / self.interval)
        bar: Iterator[tuple[T, list[URL]]] = self.logger.get_synchronous_iterator(
            iter(item_urls), total=total, desc="Opening sites", unit="items"
        )

        for n in range(1, page_total + 1):
            page_item_urls: list[tuple[T, list[URL]]] = list(itertools.islice(bar, self.interval))
            self._open_sites_for_items(page_item_urls)

            page_items = [item_urls[0] for item_urls in page_item_urls]
            page = Position(number=n, total=total, zero_fill=True)
            self._pause(items=page_items, page=page)

    def _format_and_open_sites_for_items[T: ResourceModel](
            self, items: Collection[T], fields: Collection[str]
    ) -> None:
        self._log_start(items, fields=fields)
        item_urls = self._format_urls_for_items(items, fields=fields)
        return self._open_sites_for_items(item_urls)

    def _format_urls_for_items[T: ResourceModel](
            self, items: Collection[T], fields: Collection[str]
    ) -> list[tuple[T, list[URL]]]:
        item_urls = [(item, self._format_urls_for_item(item, fields=fields)) for item in items]
        if self.unique_only:
            item_urls = self._filter_urls_for_items(item_urls)
        return item_urls

    def _format_urls_for_item(self, item: ResourceModel, fields: Collection[str]) -> list[URL]:
        return [store.format_search_url(item, fields=fields) for store in self.stores]

    def _filter_urls_for_items[T: tuple[ResourceModel, list[URL]]](self, item_urls: Iterable[T]) -> list[T]:
        unique_items: list[tuple[ResourceModel, list[URL]]] = []
        unique_urls: set[URL] = set()
        repeated: int = 0

        for item, urls in item_urls:
            if not urls:
                continue

            if all(url in unique_urls for url in urls):
                repeated += len(urls)
                continue

            urls = [url for url in urls if url not in unique_urls]
            if urls:
                unique_items.append((item, urls))
            unique_urls.update(urls)

        self.logger.print_message(f"{repeated} urls were repeated and will only be opened once.")
        return unique_items

    def _open_sites_for_items[T: ResourceModel](self, item_urls: Collection[tuple[T, Collection[URL]]]) -> None:
        self.logger.debug(f"Opening sites for {len(item_urls)} items")
        for item, urls in item_urls:
            self._open_sites_for_item(item, urls)

    def _open_sites_for_item[T: ResourceModel](self, item: T, urls: Collection[URL]) -> None:
        self.logger.debug(f"Opening {len(urls)} URLs for {self._get_item_log_value(item)!r}")
        for url in urls:
            webopen(str(url))

    def _pause(self, items: Collection[ResourceModel], page: Position) -> None:
        valid_fields = self._get_valid_fields_for_items(items)
        help_text = self._format_help_text_for_pause_page(valid_fields=valid_fields, opened=len(items))
        self.logger.print_message("\n" + help_text)

        while True:
            option = self._get_user_input(f"Enter ({page})")

            match option.casefold():
                case "":  # continue to next batch
                    break

                case "h":  # print help text
                    help_text = self._format_help_text_for_pause_page(valid_fields)
                    self.logger.print_message("\n" + help_text)

                case "r":  # re-open all sites
                    self._format_and_open_sites_for_items(items, fields=self.fields)

                # open sites for input fields for all items
                case opt if not opt.startswith("n ") and (
                    filtered_fields := self._get_filtered_fields_from_input(opt, valid_fields=set(valid_fields))
                ):
                    self._format_and_open_sites_for_items(items, fields=filtered_fields)

                case opt:
                    self._log_unrecognised_input(opt)

    def _format_help_text_for_pause_page(self, valid_fields: Collection[str], opened: int | None = None) -> str:
        header = None
        if opened is not None:
            header = colored(
                f"Opened {opened} sites. "
                "You may now search for and download the items.",
                "blue",
                attrs=["bold"],
            )

        options = {
            "<Return/Enter>": "Once you are finished with this batch, continue on to the next batch",
            "r": "Re-open all sites for the current batch of tracks",
            "<Fields>":
                "Re-open all sites for the current batch of tracks using the input list of fields, "
                "each separated by a space e.g. title artist album",
            "h": "Show this dialogue again",
        }

        field_names_message = f"\n\nValid fields for this batch: {" ".join(valid_fields)}"

        help_text = self._format_help_text(options=options, header=header)
        help_text += colored(field_names_message, "dark_grey")

        return help_text + "\n"

    @staticmethod
    def _get_valid_fields_for_items(items: Collection[ResourceModel]) -> tuple[str, ...]:
        available_fields = set(
            itertools.chain.from_iterable(cls.__tag_attributes__ for cls in {it.__class__ for it in items})
        )
        valid_fields = {field for field in available_fields if any(getattr(item, field) is not None for item in items)}

        return tuple(valid_fields)

    def _get_filtered_fields_from_input(self, inp: str, valid_fields: set[str]) -> tuple[str, ...]:
        input_fields = set(inp.split())
        filtered_fields = input_fields & valid_fields

        if filtered_fields and filtered_fields != input_fields:
            self.logger.warning(
                f"Some fields were not recognised: {", ".join(input_fields - filtered_fields)}. "
                f"Using only recognised fields: {", ".join(filtered_fields)}."
            )

        return tuple(filtered_fields)

    ###########################################################################
    ## Logging
    ###########################################################################
    def _log_start(self, items: Collection[ResourceModel], fields: Iterable[str]) -> None:
        types = sorted({f"{it.type.rstrip("s")}s" for it in items})
        types = self.logger.format_list_to_string(types)
        message = (
            f"Opening sites for {len(items)} {types} on {len(self.stores)} stores using fields: {', '.join(fields)}"
        )
        self.logger.info(message, header=1)
