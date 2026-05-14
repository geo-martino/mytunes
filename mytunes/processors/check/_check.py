import functools
import itertools
from abc import abstractmethod
from collections.abc import Sequence, Callable, Collection
from typing import Any

from pydantic import Field, PositiveInt, OnErrorOmit, validate_call

from mytunes.core.api import RemoteAPI, HasAPI, Endpoints
from mytunes.core.api.user import HasUserEndpoints
from mytunes.core.collection import CollectionModel
from mytunes.core.properties.asynch import HasAsyncOperations
from mytunes.core.properties.logger import HasProgress
from mytunes.core.properties.order import Position
from mytunes.core.properties.uri import HasURI, URI, HasMutableURI
from mytunes.processors import Processor
from mytunes.processors._flow import QuitImmediately, SkipPage
from mytunes.processors.check._match import BaseMatch, BaseInputMatch
from mytunes.processors.check.result import CheckResult
from mytunes.processors.match import Matcher
from mytunes.processors.score.string import NameScorer
from ._input.match import InputMatch as SimpleInputMatch
from ._input.page import InputPage
from ._page import CheckerPage
from ._playlist.match import SyncMatch, InputMatch as PlaylistInputMatch
from ._playlist.page import PlaylistsPage
from ...annotation import ResourceModel


class Checker[API: RemoteAPI](Processor, HasAPI[API], HasAsyncOperations, HasProgress):
    api: API = Field(
        description="The API to use for the associated remote service.",
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

    @abstractmethod
    async def _check_page[T: HasURI](
            self, page: CheckerPage[API, T]
    ) -> CheckResult[T] | Sequence[CheckResult[T]] | None:
        raise NotImplementedError

    @abstractmethod
    async def _match_page[T: HasURI](self, page: CheckerPage[API, T], **kwargs) -> CheckResult[T]:
        raise NotImplementedError

    async def _match_items[T: HasMutableURI](
            self, matchers: Sequence[BaseMatch[API, T]], items: Collection[T]
    ) -> CheckResult[T] | None:
        result: CheckResult[T] | None = None

        for matcher in matchers:
            pause_progress = self._pause_progress()
            if isinstance(matcher, BaseInputMatch):
                pause_progress.__enter__()

            next_result = await matcher.match(items)
            items = next_result.skipped
            result = next_result if result is None else result.merge(next_result)

            if isinstance(matcher, BaseInputMatch):
                pause_progress.__exit__(None, None, None)

            if not items:
                break

        return result

    ###########################################################################
    ## Logging
    ###########################################################################
    @validate_call
    def log_results(self, results: CheckResult | Sequence[OnErrorOmit[CheckResult]]) -> None:
        """Log the given check results"""
        if isinstance(results, CheckResult):
            results = [results]

        header = f"{self.source.upper()} CHECK RESULTS"
        table = CheckResult.generate_table(results=results, header=header)

        self._logger.report(table, new_line_start=True)

    def _log_start(self, items: Sequence[ResourceModel]) -> None:
        types = self._logger.format_types_to_string(items)
        message = f"Checking matches for {len(items)} {types}"
        self._logger.info(message, header=1, new_line_start=True)


class ItemChecker[API: RemoteAPI](Checker[API]):
    @staticmethod
    def _validate_items[T](func: Callable[Any, T]) -> Callable[Any, T]:
        async def _invalid_response() -> T:
            return None

        @functools.wraps(func)
        def _wrapper(self: Checker, items: Sequence, *args, **kwargs) -> T:
            items = [item for item in items if isinstance(item, HasURI)]

            if len(items) == 0:
                self._logger.extra("[yellow]No valid items to check.[\]")
                return _invalid_response()

            return func(self, items, *args, **kwargs)

        return _wrapper

    @_validate_items
    async def check[T: HasURI](self, items: Sequence[T], name: str | None = None) -> CheckResult[T] | None:
        """Check the matches for the items using only user input for checking and setting matches."""
        self._log_start(items)

        if not name:
            name = self.source

        page = InputPage(name=name, api=self.api, items=items, concurrency=self.concurrency)
        result = None

        try:
            async with page:
                result = await self._check_page(page)
        except SkipPage:
            self._logger.error("User triggered skip page with skip command")
            result = CheckResult(name=page.name, unchanged=page.items)
        except QuitImmediately:
            self._logger.error("User triggered exit with quit command")

        return result

    async def _check_page[T: HasURI](self, page: InputPage[API, T]) -> CheckResult[T] | None:
        with self._pause_progress():
            await page.pause()
        return await self._match_page(page)

    async def _match_page[T: HasURI](self, page: InputPage[API, T], **__) -> CheckResult[T]:
        matchers = [SimpleInputMatch(page=page)]
        return await self._match_items(matchers, items=page.items)

    ###########################################################################
    ## Logging
    ###########################################################################
    def _log_start(self, items: Sequence[ResourceModel]) -> None:
        types = self._logger.format_types_to_string(items)
        message = f"Checking matches for {len(items)} {types}"
        self._logger.info(message, header=1, new_line_start=True)


class CollectionChecker[API: RemoteAPI](Checker[API]):
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
                self._logger.extra("[yellow]No valid collections or items to check.[\]")
                return _invalid_response()

            return func(self, collections, *args, **kwargs)

        return _wrapper

    @_validate_collections
    async def check_on_playlists[T: HasURI](
            self, collections: Sequence[CollectionModel[T]]
    ) -> tuple[CheckResult[T], ...]:
        """
        Check the matches for the items in the given collections by creating temporary playlists
        on the remote service for checking and setting matches.
        """
        self._log_start(collections)

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
                    results += await self._check_page(page)
            except SkipPage:
                self._logger.error("User triggered skip page with skip command")
                continue
            except QuitImmediately:
                self._logger.error("User triggered exit with quit command")
                break

        return tuple(results)

    async def _check_page[T: HasURI](self, page: PlaylistsPage[API, T]) -> tuple[CheckResult[T], ...]:
        self._log_page(page)

        with self._pause_progress():
            await page.pause()

        async def _match_page(uri: URI) -> CheckResult[T]:
            return await self._match_page(page=page, uri=uri)

        task_id = self._progress.add_task("Matching changes", total=page.total)
        results = await self._run_tasks_async(map(_match_page, page.uris), task_id=task_id)
        return tuple(results)

    async def _match_page[T: HasMutableURI](self, page: PlaylistsPage[API, T], uri: URI, **__) -> CheckResult[T]:
        items = page.get_collection_items(uri)
        matchers = [
            SyncMatch(page=page, uri=uri, matcher=self.matcher),
            PlaylistInputMatch(page=page, uri=uri, matcher=self.matcher),
        ]

        return await self._match_items(matchers, items=items)

    ###########################################################################
    ## Logging
    ###########################################################################
    def _log_start(self, collections: Sequence[CollectionModel]) -> None:
        types = self._logger.format_types_to_string(collections)
        message = (
            f"Checking matches for items for {len(collections)} {types} by creating "
            f"temporary {self.source} playlists for {self.username}"
        )
        self._logger.info(message, header=1, new_line_start=True)

    def _log_page(self, page: PlaylistsPage) -> None:
        message = f"Creating {page.total} {self.source} playlists for {self.username}"
        self._logger.info(message, header=2)
