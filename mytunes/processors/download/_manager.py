"""
Processor that helps user download items from collections based on given configuration.
"""
import itertools
from collections.abc import Iterable, Collection, Sequence

from pydantic import Field, validate_call, PositiveInt, \
    conlist, AliasChoices, field_validator
from termcolor import colored
from yarl import URL

from mytunes._types import StrippedString
from mytunes.processors.download._page import StorePausePage
from mytunes.processors.download.stores import AudioStore
from .._base import Processor
from .._flow import SkipPage, QuitImmediately
from ..._models import ResourceModel
from ..._models.collection import CollectionModel
from ..._models.properties.logger import HasLogger, HasProgress
from ..._models.properties.order import Position


class StoreManager(Processor, HasLogger, HasProgress):
    """Runs operations for helping the user to download items from online stores."""

    stores: conlist(AudioStore.annotation, min_length=1) = Field(
        description="The stores to open searches on.",
        validation_alias=AliasChoices("sites", "urls"),
    )
    fields: Sequence[StrippedString] = Field(
        description="The fields to take from an item for use as the query string when opening sites.",
    )
    interval: PositiveInt = Field(
        description="The number of items to open sites for before pausing for user input.",
        default=1,
    )
    unique_only: bool = Field(
        description=(
            "Only open sites for items with unique queries. If false, sites will be opened for all items "
            "regardless of whether their query is the same as another item or not."
        ),
        default=True,
    )

    @field_validator("stores", mode="before", check_fields=True)
    @classmethod
    def _from_store_names[T](cls, names: T) -> T | list[dict[str, str]]:
        if not isinstance(names, Collection) or not all(isinstance(name, str) for name in names):
            return names
        return [dict(name=name) for name in names]

    @validate_call
    def open_sites_for_collections(self, collections: Sequence[CollectionModel]) -> None:
        """Run the manager for all items in the given ``collections``."""
        if not collections:
            self._log_skip("No collections to open sites for.")
            return

        items = tuple(itertools.chain.from_iterable(coll.items for coll in collections))
        return self.open_sites_for_items(items=items)

    @validate_call
    def open_sites_for_items[T: ResourceModel](self, items: Sequence[T] | CollectionModel[T]) -> None:
        """
        Run the manager for the given ``items``.

        Opens the formatted ``urls`` for each item in all items in the user's browser.
        """
        if isinstance(items, CollectionModel):
            items = list(items.items)

        if not items:
            self._log_skip("No items to open sites for.")
            return

        self._log_start(items, fields=self.fields)
        item_urls = self._format_urls_for_items(items, fields=self.fields)

        types = self._logger.format_types_to_string(items)
        task_id = self._progress.add_task(description=f"Opening sites for {types}", total=len(items))
        batches = list(itertools.batched(item_urls, self.interval))
        batch_total = len(batches)

        for batch_number, batch in enumerate(batches, 1):
            batch_items = [it[0] for it in batch]
            batch_urls = [it[1] for it in batch]
            page = StorePausePage(
                position=Position(number=batch_number, total=batch_total, zero_fill=True),
                task_id=task_id,
                items=batch_items,
                urls=batch_urls,
            )

            try:
                page.open_sites()
                fields = page.pause(True)
                if not fields:
                    continue

                with self._pause_progress():
                    while fields is not None:
                        page.urls = [self._format_urls_for_item(item, fields=fields) for item in page.items]
                        page.open_sites()
                        fields = page.pause(False)

            except SkipPage:
                self._logger.error("User triggered skip page with skip command")
                continue
            except QuitImmediately:
                self._logger.error("User triggered exit with quit command")
                break
            except KeyboardInterrupt:
                self._logger.error("User triggered exit with KeyboardInterrupt")
                break

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

        self._logger.debug(f"{repeated} urls were repeated and will only be opened once.")
        return unique_items

    ###########################################################################
    ## Logging
    ###########################################################################
    def _log_start(self, items: Collection[ResourceModel], fields: Iterable[str]) -> None:
        types = self._logger.format_types_to_string(items)
        message = (
            f"Opening sites for {len(items)} {types} on {len(self.stores)} stores using fields: {', '.join(fields)}"
        )
        self._logger.info(message, header=1)

    def _log_skip(self, message: str) -> None:
        self._logger.extra(colored(message, "yellow"))
