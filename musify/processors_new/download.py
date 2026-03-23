"""
Processor that helps user download songs from collections based on given configuration.
"""
import itertools
import math
from collections.abc import Iterable, Collection, Sequence
from itertools import batched
from typing import Any, Annotated
from urllib.parse import quote
from webbrowser import open as webopen

from pydantic import Field, validate_call, field_validator, HttpUrl, TypeAdapter, StringConstraints, PositiveInt
from termcolor import colored

from musify._types import StrippedString
from musify.models import AttributeModel
from musify.models.item.track import HasTracks
from musify.models.properties.name import HasName
from musify.processors_new._base import InputProcessor
from musify.processors_new.clean.string import NameCleaner


class ItemDownloadHelper(InputProcessor):
    """Runs operations for helping the user to download tracks from given collections."""
    urls: Sequence[Annotated[StrippedString, StringConstraints(pattern=r"^[^{}]*\{\}[^{}]*$")]] = Field(
        description=(
            "The template URLs for websites to open queries for. "
            "The given sites should contain exactly 1 '{}' placeholder into which the processor can place "
            "a query for the item being searched. e.g. *bandcamp.com/search?q={}&item_type=t*"
        ),
    )
    fields: Sequence[StrippedString] = Field(
        description="The fields to take from an item for use as the query string when opening sites.",
    )
    interval: PositiveInt = Field(
        description="The number of tracks to open sites for before pausing for user input.",
        default=1,
    )
    cleaner: NameCleaner | None = Field(
        description=(
            "The cleaner to use for cleaning the query parameters generated for an item. "
            "If None, no cleaning will be done."
        ),
        default=None,
    )
    unique_only: bool = Field(
        description=(
            "Only open sites for items with unique queries. If false, sites will be opened for all items "
            "regardless of whether their query is the same as another item or not."
        ),
        default=True,
    )

    @field_validator("urls", mode="after", check_fields=True)
    @classmethod
    def _validate_urls(cls, urls: Sequence[str]) -> Sequence[str]:
        # Validate that each URL contains exactly one '{}' placeholder and that the formatted URLs are valid.
        urls_formatted = [url.format("") for url in urls]
        TypeAdapter(Sequence[HttpUrl]).validate_python(urls_formatted)
        return urls

    def __call__(self, *args, **kwargs) -> None:
        return self.open_sites(*args, **kwargs)

    @validate_call
    def open_sites_for_collections(self, collections: Sequence[HasTracks]) -> None:
        """Run the download helper for all tracks in the given ``collections``."""
        tracks = tuple(itertools.chain.from_iterable(coll.tracks for coll in collections))
        return self.open_sites(tracks)

    @validate_call
    def open_sites(self, items: Sequence[AttributeModel] | HasTracks) -> None:
        """
        Run the download helper for the given ``tracks``.

        Opens the formatted ``urls`` for each item in all tracks in the user's browser.
        """
        if isinstance(items, HasTracks):
            items = items.tracks

        queries = self._format_queries_for_items(items, fields=self.fields)
        if self.unique_only:
            queries = self._filter_queries_for_items(queries)

        pages_total = math.ceil(len(queries) / self.interval)
        self.logger.info(f"Opening {len(self.urls)} sites for all {len(queries)} filtered items.")

        for page_no, page_batch in enumerate(batched(queries, self.interval), 1):
            queried, not_queried = self._open_sites_for_queries(page_batch)
            self._pause(queried=queried, not_queried=not_queried, page=page_no, total=pages_total)

    def _open_sites_for_items[T: AttributeModel](
            self, items: Collection[T], fields: Iterable[str]
    ) -> tuple[list[T], list[T]]:
        queries = self._format_queries_for_items(items, fields=fields)
        if self.unique_only:
            queries = self._filter_queries_for_items(queries)
        return self._open_sites_for_queries(queries)

    def _format_queries_for_items[T: AttributeModel](
            self, items: Collection[T], fields: Iterable[str]
    ) -> list[tuple[str, T]]:
        self.logger.info(f"Formatting queries for {len(items)} items using fields: {', '.join(fields)}")
        return [(self._format_query_for_item(item, fields=fields), item) for item in items]

    def _format_query_for_item(self, item: Any, fields: Iterable[str]) -> str:
        query_parts = []
        for field in fields:
            if (value := getattr(item, field, None)) is None:
                continue

            match value:
                case str() | HasName():
                    value = self._get_query_part(value)
                case list() | tuple() | set() | dict():
                    value = " ".join(val for val in map(self._get_query_part, value) if val)
                case _ if value is not None:
                    value = str(value)
                case _:
                    continue

            query_parts.append(value)

        return quote(" ".join(query_parts))

    def _get_query_part(self, item: Any) -> str | None:
        match item:
            case HasName():
                return self._get_query_part(item.name)
            case str() if self.cleaner is not None:
                return self.cleaner.clean(item)
            case str():
                return item
            case _:
                return None

    def _filter_queries_for_items[T: AttributeModel](self, queries: Iterable[tuple[str, T]]) -> list[tuple[str, T]]:
        result: dict[str, T] = {}
        repeated: int = 0

        for query, item in queries:
            if not query:
                continue

            if query in result:
                repeated += 1
                continue

            result[query] = item

        self.logger.warning(f"{repeated} queries were repeated and will only be opened once.")
        return list(result.items())

    def _open_sites_for_queries[T: AttributeModel](self, queries: Iterable[tuple[str, T]]) -> tuple[list[T], list[T]]:
        queried = []
        not_queried = []

        for query, item in queries:
            if not query:
                item_log = item.name if isinstance(item, HasName) else item
                self.logger.debug(f"Could not get query for item: {item_log}")
                not_queried.append(item)
                continue

            self.logger.debug(f"Opening {len(self.urls)} URLs with query: {query}")
            for url in self.urls:
                webopen(url.format(query))
            queried.append(item)

        return queried, not_queried

    def _pause[T: AttributeModel](self, queried: Collection[T], not_queried: Collection[T], page: int, total: int):
        valid_fields = self._get_valid_fields_for_items(queried) | self._get_valid_fields_for_items(not_queried)
        help_text = self._format_help_text_for_items(not_queried=len(not_queried), valid_fields=valid_fields)
        self.logger.print_message("\n" + help_text)

        while True:
            match self._get_user_input(f"Enter ({page}/{total})").casefold():
                case "":  # continue to next batch
                    break

                case "h":  # print help text
                    self.logger.print_message("\n" + help_text)

                case "r":  # re-open all sites
                    self._open_sites_for_items(queried, fields=self.fields)

                # open sites for fields in input for all items
                case inp if not inp.startswith("n ") and (
                    filtered_fields := self._get_filtered_fields_from_input(inp, valid_fields=valid_fields)
                ):
                    self._open_sites_for_items(queried, fields=filtered_fields)

                # open sites for fields in input but only for items which sites could not be opened for
                case inp if inp.startswith("n ") and (
                    filtered_fields := self._get_filtered_fields_from_input(
                        inp.lstrip("n").strip(), valid_fields=valid_fields
                    )
                ):
                    self._open_sites_for_items(not_queried, fields=filtered_fields)

                case inp:
                    self.logger.warning(f"Unrecognised input: {inp}. Enter 'h' to see valid options.")

    def _format_help_text_for_items(self, not_queried: int, valid_fields: Collection[str]) -> str:
        opened = len(self.urls) * (self.interval - not_queried)
        not_opened = f" - Could not open sites for {not_queried} tracks. " if not_queried else ". "

        header = colored(
            f"Opened {opened} sites" +
            not_opened +
            "You may now search for and download the tracks.",
            "blue",
            attrs=["bold"],
        )
        options = {
            "<Return/Enter>": "Once you are finished with this batch, continue on to the next batch",
            "r": "Re-open all sites for the current batch of tracks",
            "<Fields>":
                "Re-open all sites for the current batch of tracks using the input list of fields, "
                "each separated by a space e.g. title artist album",
        }

        if not_queried:
            options["n <Fields>"] = (
                f"Same as above, but only open sites for the {not_queried} tracks "
                "which sites could not be opened for"
            )
        options["h"] = "Show this dialogue again"

        help_text = self._format_help_text(options=options, header=header)
        help_text += colored(f"\n\nValid fields for this batch: {" ".join(valid_fields)}", "dark_grey")

        return help_text + "\n"

    @staticmethod
    def _get_valid_fields_for_items(items: Collection[AttributeModel]) -> set[str]:
        available_fields = set(
            itertools.chain.from_iterable(cls.__tag_attributes__ for cls in {it.__class__ for it in items})
        )
        valid_fields = {field for field in available_fields if any(getattr(item, field) is not None for item in items)}

        return valid_fields

    def _get_filtered_fields_from_input(self, inp: str, valid_fields: set[str]) -> set[str]:
        input_fields = set(inp.split())
        filtered_fields = input_fields & valid_fields

        if filtered_fields and filtered_fields != input_fields:
            self.logger.warning(
                f"Some fields were not recognised: {", ".join(input_fields - filtered_fields)}. "
                f"Using only recognised fields: {", ".join(filtered_fields)}."
            )

        return filtered_fields
