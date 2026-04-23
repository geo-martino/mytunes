import functools
import itertools
from collections.abc import Sequence, Callable, Collection
from typing import Any

from pydantic import Field, PositiveInt
from termcolor import colored

from mytunes.core.api import RemoteAPI, HasAPI, Endpoints
from mytunes.core.api.user import HasUserEndpoints
from mytunes.core.collection import CollectionModel
from mytunes.core.properties.asynch import HasAsyncOperations
from mytunes.core.properties.logger import HasProgress
from mytunes.core.properties.order import Position
from mytunes.core.properties.uri import HasURI, URI, HasMutableURI
from mytunes.processors._flow import QuitImmediately, SkipPage
from mytunes.processors.check._match import BaseMatch
from mytunes.processors.check.result import CheckResult
from mytunes.processors.match import Matcher
from mytunes.processors.score.string import NameScorer
from ._input.page import InputPage
from ._page import CheckerPage
from ._playlist.match import SyncMatch, InputMatch as PlaylistInputMatch
from ._input.match import InputMatch as SimpleInputMatch
from ._playlist.page import PlaylistsPage
from mytunes.processors import Processor
from ...annotation import ResourceModel


class Checker[API: RemoteAPI](Processor, HasAPI[API], HasProgress, HasAsyncOperations):
    api: API = Field(
        description="The API to use for checking matches.",
    )
    matcher: Matcher = Field(
        description=(
            "The matcher to use for confirming closest matches returned by the API "
            "when comparing changes in playlists on collection matching."
        ),
        default=Matcher(scorers=[NameScorer()]),
    )
    interval: PositiveInt = Field(
        description="The number of collections to process before pausing for user input when matching collections.",
        default=10,
    )

    @property
    def source(self) -> str:
        """The log name of the remote service that this searcher is running on."""
        return self.api.source

    @property
    def username(self) -> str:
        """The user to create playlists for."""
        user = self.api.user if isinstance(self.api, Endpoints | HasUserEndpoints) else None
        return user.name if user is not None else "the current user"

    ###########################################################################
    ## Item match
    ###########################################################################
    @staticmethod
    def _validate_items[T](func: Callable[Any, T]) -> Callable[Any, T]:
        async def _invalid_response() -> T:
            return None

        @functools.wraps(func)
        def _wrapper(self: Checker, items: Sequence, *args, **kwargs) -> T:
            items = [item for item in items if isinstance(item, HasURI)]

            if len(items) == 0:
                self._logger.extra(colored("No valid items to check.", "yellow"))
                return _invalid_response()

            return func(self, items, *args, **kwargs)

        return _wrapper

    @_validate_items
    async def check_items[T: HasURI](self, items: Sequence[T], name: str | None = None) -> CheckResult[T] | None:
        """Check the matches for the items using only user input for checking and setting matches."""
        self._log_item_start(items)

        page = InputPage(name=name, api=self.api, items=items, concurrency=self.concurrency)

        try:
            async with page:
                return await self._check_item_page(page)
        except SkipPage:
            self._logger.error("User triggered skip page with skip command")
        except QuitImmediately:
            self._logger.error("User triggered exit with quit command")

    async def _check_item_page[T: HasURI](self, page: InputPage[API, T]) -> CheckResult[T] | None:
        with self._pause_progress():
            all_valid = await page.pause()

        matcher = SimpleInputMatch(page=page)
        if all_valid:
            return CheckResult(name=matcher.name, unchanged=page.items)

        await self._match_items([matcher], items=page.items)

    ###########################################################################
    ## Playlist match
    ###########################################################################
    @staticmethod
    def _validate_collections[T](func: Callable[Any, T]) -> Callable[Any, T]:
        async def _invalid_response() -> T:
            return tuple()

        @functools.wraps(func)
        def _wrapper(self: Checker, collections: Sequence[CollectionModel], *args, **kwargs) -> T:
            collections = [
                coll for coll in collections
                if coll.total > 0 and any(isinstance(item, HasURI) for item in coll.items)
            ]

            if len(collections) == 0:
                self._logger.extra(colored("No valid collections or items to check.", "yellow"))
                return _invalid_response()

            return func(self, collections, *args, **kwargs)

        return _wrapper

    @_validate_collections
    async def check_collections_on_playlists[T: HasURI](
            self, collections: Sequence[CollectionModel[T]]
    ) -> tuple[CheckResult[T], ...]:
        """
        Check the matches for the items in the given collections by creating temporary playlists
        on the remote service for checking and setting matches.
        """
        self._log_playlist_start(collections)

        task_id = self._progress.add_task(description="Creating playlists", total=len(collections))
        batches = list(itertools.batched(collections, self.interval))
        batch_total = len(batches)

        results: list[CheckResult[T]] = []
        for batch_number, batch in enumerate(batches, 1):
            page = PlaylistsPage(
                position=Position(number=batch_number, total=batch_total, zero_fill=True),
                api=self.api,
                items=batch,
                task_id=task_id,
                concurrency=self.concurrency,
            )

            try:
                async with page:
                    results += await self._check_playlist_page(page)
            except SkipPage:
                self._logger.error("User triggered skip page with skip command")
                continue
            except QuitImmediately:
                self._logger.error("User triggered exit with quit command")
                break

        return tuple(results)

    async def _check_playlist_page[T: HasURI](self, page: PlaylistsPage[API, T]) -> tuple[CheckResult[T], ...]:
        self._log_playlist_page(page)

        with self._pause_progress():
            await page.pause()

        async def _match_playlist(uri: URI) -> tuple[str, CheckResult[T]]:
            name = page.get_playlist_name(uri)
            return name, await self._match_playlist(page=page, uri=uri)

        task_id = self._progress.add_task("Matching changes", total=page.total)
        results = await self._run_tasks_async(map(_match_playlist, page.uris), task_id=task_id)
        return tuple(results)

    async def _match_playlist[T: HasMutableURI](self, page: PlaylistsPage[API, T], uri: URI) -> CheckResult[T]:
        items = page.get_collection_items(uri)
        matchers = [
            SyncMatch(page=page, uri=uri, matcher=self.matcher),
            PlaylistInputMatch(page=page, uri=uri, matcher=self.matcher),
        ]

        return await self._match_items(matchers, items=items)

    ###########################################################################
    ## Common functionality
    ###########################################################################
    @staticmethod
    async def _match_items[T: HasMutableURI](
            matchers: Sequence[BaseMatch[API, T]], items: Collection[T]
    ) -> CheckResult[T] | None:
        result: CheckResult[T] | None = None

        for matcher in matchers:
            next_result = await matcher.match(items)
            items = next_result.skipped
            result = next_result if result is None else result.merge(next_result)

            if not items:
                break

        return result

    ###########################################################################
    ## Logging + validation
    ###########################################################################
    def log_results(self, results: CheckResult | Sequence[CheckResult]) -> None:
        """Log the given check results"""
        if isinstance(results, CheckResult):
            results = [results]

        header = f"{self.source.upper()} CHECK RESULTS"
        table = CheckResult.generate_table(results=results, header=header)

        self._logger.report(table, new_line_start=True, new_line_end=True)

    def _log_item_start(self, items: Sequence[ResourceModel]) -> None:
        types = self._logger.format_types_to_string(items)
        message = f"Checking matches for {len(items)} {types}"
        self._logger.info(message, header=1)

    def _log_playlist_start(self, collections: Sequence[CollectionModel]) -> None:
        types = self._logger.format_types_to_string(collections)
        message = (
            f"Checking matches for items for {len(collections)} {types} by creating "
            f"temporary {self.source} playlists for {self.username}"
        )
        self._logger.info(message, header=1)

    def _log_playlist_page(self, page: CheckerPage) -> None:
        message = f"Creating {page.total} {self.source} playlists for {self.username}"
        self._logger.info(message, header=2)
