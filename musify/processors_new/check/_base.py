import itertools
import math
from collections.abc import Mapping, Sequence, Iterable
from contextlib import suppress

from pydantic import Field, PositiveInt
from termcolor import colored

from musify.models import ResourceModel
from musify.models.api import HasAPI
from musify.models.collection import CollectionModel
from musify.models.properties.order import Position
from musify.models.properties.uri import HasURI
from musify.models.user import RemoteUser
from musify.processors_new._base import InputProcessor
from musify.processors_new.check._exception import SkipPage, QuitImmediately
from musify.processors_new.check._match.inputs import InputMatch
from musify.processors_new.check._match.playlist import PlaylistMatch
from musify.processors_new.check._page import CheckerPage, _ApiT
from musify.processors_new.check.result import CheckResult
from musify.processors_new.match import Matcher
from musify.processors_new.match.score.string import NameScorer


class Checker[API: _ApiT](InputProcessor, HasAPI):
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
    def user(self) -> RemoteUser | None:
        """The user to create playlists for."""
        return self.api.user

    async def check[T: ResourceModel](self, collections: Sequence[CollectionModel[T]]) -> dict[str, CheckResult[T]]:
        """Check the matches for the given collection and return the results."""
        if not (collections := self._validate_collections(collections)):
            return {}

        self._log_start(collections)

        total = len(collections)
        bar = self.logger.get_synchronous_iterator(
            iter(collections), total=total, desc="Creating playlists", unit="playlists"
        )

        results: dict[str, CheckResult[T]] = {}
        for n in range(1, math.ceil(total / self.interval) + 1):
            try:
                results |= await self._check_page(bar, n=n, total=total)
            except KeyboardInterrupt:
                self.logger.error("User triggered exit with KeyboardInterrupt")
                break
            except QuitImmediately:
                self.logger.error("User triggered exit with quit command")
                break

        return results

    async def _check_page[T: ResourceModel](
            self, collections: Iterable[CollectionModel[T]], n: int, total: int,
    ) -> dict[str, CheckResult[T]]:
        page = CheckerPage(
            position=Position(number=n, total=total, zero_fill=True),
            api=self.api,
            collections=itertools.islice(collections, self.interval)
        )

        results: dict[str, CheckResult[T]] = {}
        async with page:
            await page.setup_playlists()

            with suppress(SkipPage):
                await page.pause()
                results |= await self._match_page(page)

        return results

    async def _match_page[T: ResourceModel](self, page: CheckerPage[API, T]) -> dict[str, CheckResult[T]]:
        results: dict[str, CheckResult[T]] = {}

        for uri in page.uris:
            name = page.get_playlist_name(uri)
            items = page.get_collection_items(uri)

            matcher = PlaylistMatch(page=page, matcher=self.matcher)
            playlist_result = await matcher.match(items=items, uri=uri, name=name)
            if not playlist_result.skipped:
                results[name] = playlist_result
                continue

            try:
                matcher = InputMatch(page=page, matcher=self.matcher)
                input_result = await matcher.match(items=playlist_result.skipped, uri=uri, name=name)
                results[name] = playlist_result.merge_results(input_result)
            except SkipPage:  # catch this here so we can still return current set of results
                break

        return results

    ###########################################################################
    ## Logging + validation
    ###########################################################################
    def log_results(self, results: Mapping[str, CheckResult]) -> None:
        """Log the given check results"""
        header = f"{self.source.upper()} CHECK RESULTS"
        table = CheckResult.generate_table(results=results, header=header)
        self.logger.report(table)

    def _log_start(self, collections: Sequence[CollectionModel]) -> None:
        collection_types = sorted({
            collection.type.rstrip("s") + "s" for collection in collections if isinstance(collection, ResourceModel)
        })

        collection_types_str = ", ".join(collection_types[:-1])
        if collection_types_str:
            collection_types_str = " & ".join([collection_types_str, collection_types[-1]])
        else:
            collection_types_str = collection_types[0]

        username = self.user.name if self.user is not None else "the current user"
        message = (
            f"Checking items in {len(collections)} {collection_types_str} by creating "
            f"temporary {self.source} playlists for {username}"
        )
        self.logger.info(message, header=1)

    def _validate_collections(self, collections: Sequence[CollectionModel]) -> Sequence[CollectionModel]:
        collections = [
            coll for coll in collections
            if coll.count > 0 and any(isinstance(item, HasURI) for item in coll.items)
        ]
        if len(collections) == 0:
            self.logger.extra(colored("No valid collections or items to check.", "yellow"))

        return collections
