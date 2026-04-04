import itertools
from collections.abc import Mapping, Sequence, AsyncGenerator

from pydantic import Field, PositiveInt
from termcolor import colored

from musify.models import ResourceModel
from musify.models.api import HasAPI
from musify.models.collection import CollectionModel
from musify.models.properties.asynch import HasAsyncOperations
from musify.models.properties.logger import HasLogger
from musify.models.properties.order import Position
from musify.models.properties.uri import HasURI, URI
from musify.processors._base import Processor
from musify.processors._exception import QuitImmediately, SkipPage
from musify.processors.check._match.inputs import InputMatch
from musify.processors.check._match.playlist import PlaylistMatch
from musify.processors.check._page import CheckerPage, _ApiT
from musify.processors.check.result import CheckResult
from musify.processors.match import Matcher
from musify.processors.match.score.string import NameScorer


class Checker[API: _ApiT](Processor, HasLogger, HasAPI[API], HasAsyncOperations):
    api: API = Field(
        description="The API to use for checking matches.",
    )
    matcher: Matcher = Field(
        description=(
            "The matcher to use for confirming closest matches returned by the API "
            "when comparing changes in playlists"
        ),
        default_factory=lambda: Matcher(scorers=[NameScorer()]),
    )
    interval: PositiveInt = Field(
        description="The number of playlists to create before pausing for user input.",
        default=10,
    )

    @property
    def source(self) -> str:
        """The log name of the remote service that this searcher is running on."""
        return self.api.source.title()

    @property
    def username(self) -> str:
        """The user to create playlists for."""
        return self.api.user.name if self.api.user is not None else "the current user"

    async def check[T: ResourceModel](self, collections: Sequence[CollectionModel[T]]) -> dict[str, CheckResult[T]]:
        """Check the matches for the given collection and return the results."""
        if not (collections := self._validate_collections(collections)):
            return {}

        self._log_start(collections)

        task_id = self.logger.progress.add_task(description="Creating playlists", total=len(collections))
        batches = list(itertools.batched(collections, self.interval))
        batch_total = len(batches)

        results: dict[str, CheckResult[T]] = {}
        for batch_number, batch in enumerate(batches, 1):

            page = CheckerPage(
                position=Position(number=batch_number, total=batch_total, zero_fill=True),
                api=self.api,
                collections=batch,
                task_id=task_id,
                concurrency=self.concurrency,
            )

            try:
                self._log_page(page)
                async for name, result in self._check_page(page):
                    results[name] = result
            except SkipPage:
                self.logger.error("User triggered skip page with skip command")
                continue
            except QuitImmediately:
                self.logger.error("User triggered exit with quit command")
                break
            except KeyboardInterrupt:
                self.logger.error("User triggered exit with KeyboardInterrupt")
                break

        return results

    async def _check_page[T: ResourceModel](
        self, page: CheckerPage[API, T]
    ) -> AsyncGenerator[tuple[str, CheckResult[T]]]:
        async with page:
            await page.pause()

            task_id = self.logger.progress.add_task("Matching changes", total=page.count)
            with self.logger:
                for name, uri in zip(page.names, page.uris, strict=True):
                    result = await self._match_page(page, uri=uri)
                    yield name, result

                    self.logger.progress.advance(task_id, advance=1)

            self.logger.progress.remove_task(task_id)

    async def _match_page[T: ResourceModel](self, page: CheckerPage[API, T], uri: URI) -> CheckResult[T]:
        items = page.get_collection_items(uri)
        matcher = PlaylistMatch(page=page, items=items, uri=uri, matcher=self.matcher)
        playlist_result = await matcher.match()
        if not playlist_result.skipped:
            return playlist_result

        self.logger.progress.stop()
        matcher = InputMatch(page=page, items=playlist_result.skipped, uri=uri, matcher=self.matcher)
        input_result = await matcher.match()
        self.logger.progress.start()
        return playlist_result.merge_results(input_result)

    ###########################################################################
    ## Logging + validation
    ###########################################################################
    def log_results(self, results: Mapping[str, CheckResult]) -> None:
        """Log the given check results"""
        header = f"{self.source.upper()} CHECK RESULTS"
        table = CheckResult.generate_table(results=results, header=header)
        self.logger.report(table)

    def _log_start(self, collections: Sequence[CollectionModel]) -> None:
        types = sorted({f"{it.type.rstrip("s")}s" for it in collections if isinstance(it, ResourceModel)})
        types = self.logger.format_list_to_string(types)

        message = (
            f"Checking items in {len(collections)} {types} by creating "
            f"temporary {self.source} playlists for {self.username}"
        )
        self.logger.info(message, header=1)

    def _log_page(self, page: CheckerPage) -> None:
        message = f"Creating {page.count} {self.source} playlists for {self.username}"
        self.logger.info(message, header=2)

    def _validate_collections(self, collections: Sequence[CollectionModel]) -> Sequence[CollectionModel]:
        collections = [
            coll for coll in collections
            if coll.count > 0 and any(isinstance(item, HasURI) for item in coll.items)
        ]
        if len(collections) == 0:
            self.logger.extra(colored("No valid collections or items to check.", "yellow"))

        return collections
