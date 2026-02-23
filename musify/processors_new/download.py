"""
Processor that helps user download songs from collections based on given configuration.
"""
import itertools
import math
import re
from collections.abc import Iterable, Collection, Sequence
from itertools import batched
from typing import Any, Annotated
from urllib.parse import quote
from webbrowser import open as webopen

from pydantic import Field, validate_call, field_validator, HttpUrl, TypeAdapter, StringConstraints, PositiveInt
from termcolor import colored

from musify._types import StrippedString
from musify.models.item.track import HasTracks, Track
from musify.models.properties.name import HasName
from musify.processors_new._base import InputProcessor


class ItemDownloadHelper(InputProcessor):
    """Runs operations for helping the user to download tracks from given collections."""
    urls: Sequence[Annotated[StrippedString, StringConstraints(pattern="^[^{}]*\{\}[^{}]*$")]] = Field(
        description=(
            "The template URLs for websites to open queries for. "
            "The given sites should contain exactly 1 '{}' placeholder into which the processor can place "
            "a query for the item being searched. e.g. *bandcamp.com/search?q={}&item_type=t*"
        ),
        default_factory=tuple,
    )
    fields: Sequence[StrippedString] | None = Field(
        description="The default fields to take from an item for use as the query string when initially opening sites.",
        default=None,
    )
    interval: PositiveInt = Field(
        description="The number of tracks to open sites for before pausing for user input.",
        default=1,
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
    def open_sites(self, tracks: Sequence[Track] | HasTracks) -> None:
        """
        Run the download helper for the given ``tracks``.

        Opens the formatted ``urls`` for each item in all tracks in the user's browser.
        """
        if isinstance(tracks, HasTracks):
            tracks = tracks.tracks

        pages_total = math.ceil(len(tracks) / self.interval)

        for page, page_tracks in enumerate(batched(tracks, self.interval), 1):
            not_queried = self._open_sites_for_tracks(tracks=page_tracks, fields=self.fields)
            self._pause(tracks=page_tracks, not_queried=not_queried, page=page, total=pages_total)

    def _open_sites_for_tracks[T: Track](self, tracks: Iterable[T], fields: Iterable[str]) -> list[T]:
        not_queried = []
        for item in tracks:
            queried = self._open_sites_for_item(item=item, fields=fields)
            if not queried:
                not_queried.append(item)

        return not_queried

    def _open_sites_for_item(self, item: Any, fields: Iterable[str]) -> bool:
        query_parts = []
        for field in fields:
            if (value := getattr(item, field, None)) is None:
                continue

            if isinstance((value_many := getattr(item, field, None)), (list, tuple)):
                value = next(iter(value_many), None)

            if isinstance(value, HasName):
                value = value.name
            elif isinstance(value, (tuple, set, list, dict)):
                value = " ".join(v.name if isinstance(v, HasName) else v for v in value)

            if value is not None:
                query_parts.append(str(value))

        query = quote(" ".join(query_parts))
        if not query:
            item_log = item.name if isinstance(item, HasName) else item
            self.logger.debug(f"Could not get query for item: {item_log}")
            return False

        self.logger.debug(f"Opening {len(self.urls)} URLs with query: {query}")
        for url in self.urls:
            webopen(url.format(query))

        return True

    def _pause[T: Track](self, tracks: Collection[T], not_queried: Collection[T], page: int, total: int):
        opened = len(self.urls) * (self.interval - len(not_queried))
        not_opened = f" - Could not open sites for {len(not_queried)} tracks. " if not_queried else ". "

        available_fields = set(
            itertools.chain.from_iterable(cls.__tag_attributes__ for cls in {it.__class__ for it in tracks})
        )
        valid_fields = {field for field in available_fields if any(getattr(item, field) is not None for item in tracks)}

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
                f"Same as above, but only open sites for the {len(not_queried)} tracks "
                "which sites could not be opened for"
            )
        options["h"] = "Show this dialogue again"

        help_text = self._format_help_text(options=options, header=header)
        help_text += f"\n\t\33[90mValid fields for this batch: {" ".join(valid_fields)}\33[0m\n"

        self.logger.print_message("\n" + help_text)
        while True:
            match self._get_user_input(f"Enter ({page}/{total})").casefold():
                case "":
                    break
                case "h":  # print help text
                    self.logger.print_message("\n" + help_text)
                case "r":  # re-open all sites
                    self._open_sites_for_tracks(tracks=tracks, fields=self.fields)
                case inp if (
                    filtered_fields := (fields := set(re.sub(r"^n ", "", inp).split())) & valid_fields
                ):
                    if filtered_fields != fields:
                        self.logger.warning(
                            f"Some fields were not recognised: {", ".join(fields - filtered_fields)}. "
                            f"Using recognised fields: {", ".join(filtered_fields)}."
                        )

                    self._open_sites_for_tracks(
                        tracks=not_queried if inp.startswith("n ") else tracks, fields=filtered_fields
                    )
                case inp:
                    self.logger.warning(f"Unrecognised input: {inp}. Please enter one of the valid options.")
