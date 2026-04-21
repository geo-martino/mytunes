import textwrap
from collections.abc import Sequence, MutableSequence, Collection, Iterable
from typing import Self, Any, Annotated

from pydantic import Field, validate_call, model_validator, field_validator
from termcolor import colored

from mytunes._types import TO_TUPLE
from mytunes.processors.match import Matcher
from ._base import Processor
from .._base.resource import ResourceModel
from ..core.api import RemoteAPI, HasAPI
from ..core.api.search import HasSearchEndpoints
from mytunes.core.collection import CollectionModel, RemoteCollection
from mytunes.core.album import AlbumCollection
from mytunes.exception import MyTunesValidationError
from mytunes.core.properties.asynch import HasAsyncOperations
from mytunes.core.properties.file import IsFile, IsLocalFile
from mytunes.core.properties.logger import HasProgress, HasLogger
from mytunes.core.properties.name import HasName
from mytunes.core.properties.uri import HasURI, HasMutableURI
from ..core.remote import RemoteResource
from mytunes.result import TotalCountResult, LenLogFormatter
from .._utils import truncate_string


class SearchResult[T: Any](TotalCountResult):
    """Stores the results of the searching process."""
    matches: Annotated[
        Sequence[T],
        TO_TUPLE,
        LenLogFormatter(condition=lambda x: False),  # never log this attribute
    ] = Field(
        description=(
            "The matches from the API that were found in the search. This will match the items in the `matched` "
            "attribute so that the corresponding items can be easily mapped together."
        ),
        default_factory=tuple
    )
    matched: Annotated[
        Sequence[T],
        TO_TUPLE,
        LenLogFormatter(
            width=6, alignment="right", colour="blue", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LenLogFormatter(
            width=6, alignment="right", colour="green", colour_attributes=["bold"], condition=lambda x: x > 0
        ),
    ] = Field(
        description=(
            "The given items which were matched during the search. This will match the items in the `matches` "
            "attribute so that the corresponding items can be easily mapped together."
        ),
        default_factory=tuple
    )
    unmatched: Annotated[
        Sequence[T],
        TO_TUPLE,
        LenLogFormatter(
            width=6, alignment="right", colour="green", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LenLogFormatter(
            width=6, alignment="right", colour="red", colour_attributes=["bold"], condition=lambda x: x > 0
        ),
    ] = Field(
        description="The items for which matches were not found from the search.",
        default_factory=tuple
    )
    skipped: Annotated[
        Sequence[T],
        LenLogFormatter(
            width=6, alignment="right", colour="green", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LenLogFormatter(
            width=6, alignment="right", colour="blue", colour_attributes=["bold"], condition=lambda x: x > 0
        ),
    ] = Field(
        description="The items which were skipped during the search.",
        default_factory=tuple
    )

    @model_validator(mode="after")
    def _validate_matches_are_equal(self) -> Self:
        if len(self.matches) != len(self.matched):
            raise MyTunesValidationError("The number of matches must be equal to the number of matched items.")
        return self


type _ApiT = RemoteAPI | HasSearchEndpoints


class Searcher[API: _ApiT](Processor, HasAPI[API], HasProgress, HasAsyncOperations):
    api: API = Field(
        description="The API to use when searching for matches.",
    )
    matcher: Matcher | None = Field(
        description="The matcher to use for confirming closest matches returned by the API",
        default=None,
    )

    skip_if_has_uri: bool = Field(
        description="Skip searching for matches if the item already has a URI assigned.",
        default=True,
    )

    assign_uri: bool = Field(
        description=(
            "Whether to assign the URI of the match to the given items. "
            "This also applies to the items within a collection if the given item is a collection."
        ),
        default=True,
    )

    items_only_on_collections: bool = Field(
        description=(
            "Whether to always search for collections by searching for the items individually instead of the "
            "collection as a whole. "
            "In case of the latter, items will be matched to the items in the matched collection. "
            "This overrides all other settings related to searching for collections if set to True."
        ),
        default=False,
    )
    compilation_albums_as_tracks_only: bool = Field(
        description=(
            "Whether to always search for compilation albums by searching for the individual tracks instead of the "
            "album as a whole. "
            "In case of the latter, tracks will be matched to the tracks in the matched album."
        ),
        default=False,
    )
    keep_matching_collection_items: bool = Field(
        description=(
            "If matching a collection and there are still unmatched items, searching for matches "
            "for the outstanding items individually. "
            "This only applies if the collection has been searched for as a whole with items matched "
            "to that result first."
        ),
        default=False,
    )

    @field_validator("api", mode="after", check_fields=True)
    @classmethod
    def _validate_api_has_necessary_endpoints(cls, api: _ApiT) -> _ApiT:
        if not isinstance(api, RemoteAPI):
            raise MyTunesValidationError(f"API must be an instance of RemoteAPI, got {type(api).__name__!r}")
        if not isinstance(api, HasSearchEndpoints):
            raise MyTunesValidationError(f"API does not support search endpoints")

        return api

    @property
    def source(self) -> str:
        """The name of the remote service that this searcher is running on."""
        return self.api.source

    ###########################################################################
    ## Search: items
    ###########################################################################
    @validate_call
    async def search_item[T: ResourceModel](self, item: T) -> T | None:
        """Search for matches for the given item and return the matching result if found"""
        if self._should_skip(item):
            self._log_skip(f"Cannot process {self._get_item_log_name(item)}")
            return

        self._log_start([item], default_type="item")
        return await self._query_and_match(item)

    @validate_call
    async def search_items[T: ResourceModel](self, items: Sequence[T]) -> SearchResult[T]:
        """Search for matches for the given items and return the results."""
        if len(items) == 0:
            self._log_skip("No items to search.")
            return SearchResult()

        self._log_start(items, default_type="items")
        return await self._search_items(items)

    async def _search_items[T: ResourceModel](self, items: Iterable[T]) -> SearchResult[T]:
        matches = []
        matched = []
        unmatched = []

        async def _search_and_match_item(item: T) -> None:
            match = await self._query_and_match(item)
            if match is not None:
                matched.append(item)
                matches.append(match)
            else:
                unmatched.append(item)

        items, skipped = self._split_items(items)

        task_id = self._progress.add_task(description=f"Searching", total=len(items))
        await self._run_tasks_async(map(_search_and_match_item, items), task_id=task_id)

        return SearchResult(matches=matches, matched=matched, unmatched=unmatched, skipped=skipped)

    def _match_items[T: ResourceModel](
            self, items: Iterable[T], results: Iterable[T], skipped: Iterable[T] = ()
    ) -> SearchResult[T]:
        results = list(results)
        if not results:
            return SearchResult(unmatched=tuple(items), skipped=tuple(skipped))

        matched = []
        matches = []
        unmatched = []

        for item in items:
            match = self._match_item(item, results)
            if match is not None:
                matched.append(item)
                matches.append(match)
            else:
                unmatched.append(item)

        return SearchResult(matches=matches, matched=matched, unmatched=unmatched, skipped=skipped)

    ###########################################################################
    ## Search: collections
    ###########################################################################
    @validate_call
    async def search_collection[T: ResourceModel](self, collection: CollectionModel) -> SearchResult[T] | None:
        """Search for matches for the given collection and return the results."""
        if self._should_skip(collection):
            self._log_skip(f"Cannot process {self._get_item_log_name(collection)}")
            return

        self._log_start([collection], default_type="collection")
        _, result = await self._search_collection(collection)
        return result

    @validate_call
    async def search_collections[T: ResourceModel](
            self, collections: Sequence[CollectionModel]
    ) -> tuple[tuple[str, SearchResult[T]], ...]:
        """Search for matches for the given collection and return the results per collection."""
        if len(collections) == 0 or sum(collection.count for collection in collections) == 0:
            self._log_skip("No collections or items to search.")
            return tuple()

        collections, _ = self._split_items(collections)
        if not collections:
            self._log_skip(f"Cannot process of the given collections")
            return tuple()

        self._log_start(collections, default_type="collections")

        async def _search_collection(collection: CollectionModel[T]) -> tuple[str, SearchResult[T]]:
            return await self._search_collection(collection)

        task_id = self._progress.add_task(description=f"Searching", total=len(collections))
        results = await self._run_tasks_async(map(_search_collection, collections), task_id=task_id)
        return tuple(results)

    async def _search_collection[T: ResourceModel](
            self, collection: CollectionModel[T]
    ) -> tuple[str, SearchResult[T]]:
        name = collection.name if isinstance(collection, HasName) else str(id(collection))

        if self._should_search_on_items_only(collection):
            return name, await self._search_items(collection.items)
        collection: ResourceModel | CollectionModel  # type checked in the above condition

        match = await self._query_and_match(collection)
        match = await self._extend_collection_items(match)
        if match is None or not isinstance(match, CollectionModel):
            return name, await self._search_items(collection.items)

        items, skipped = self._split_items(collection.items)
        result = self._match_items(items, list(match.items), skipped)
        if self.keep_matching_collection_items and result.unmatched:
            result = await self._search_from_result(result)

        return name, result

    async def _search_from_result[T: ResourceModel](self, result: SearchResult[T]) -> SearchResult[T]:
        # attempt to search for the unmatched items from the given search result
        # we pop items from the result lists as we go to match the same order as the given items
        # for consistency in ordering
        result_matches = list(result.matches)
        result_matched = list(result.matched)

        matches = []
        matched = []
        unmatched = []

        async def _search_and_match_item(item: Any) -> None:
            if item in result_matched:
                matches.append(result_matches.pop(0))
                matched.append(result_matched.pop(0))

            match = await self._query_and_match(item)
            if match is not None:
                matched.append(item)
                matches.append(match)
            else:
                unmatched.append(item)

        task_id = self._progress.add_task(description=f"Searching", total=len(result.unmatched))
        await self._run_tasks_async(map(_search_and_match_item, result.unmatched), task_id=task_id)

        return SearchResult(matches=matches, matched=matched, unmatched=unmatched, skipped=result.skipped)

    async def _extend_collection_items[T: RemoteResource | RemoteCollection](self, collection: T) -> T:
        if not isinstance(collection, RemoteCollection):
            try:
                collection = await collection.reload(self.api)
            except AttributeError:
                message = "Cannot reload collection: valid endpoints not configured for this resource type"
                self._log_debug(collection, message=message)
                return collection

            if isinstance(collection, RemoteResource) and not isinstance(collection, RemoteCollection):
                message = "API did not return a collection when trying to extend items in collection"
                self._log_debug(collection, message=message)
                return collection

        try:
            await collection.extend(self.api)
        except AttributeError:
            message = "Cannot extend items in collection: valid endpoints not configured for this resource type"
            self._log_debug(collection, message=message)

        return collection

    ###########################################################################
    ## Query and match utilities
    ###########################################################################
    async def _query(self, item: ResourceModel) -> list[RemoteResource] | None:
        async with self.concurrency:
            results = await self.api.search.query_item(item)

        if not results:
            self._log_debug(item, message="No results found")
            return None

        self._log_debug(item, message=f"Found {len(results)} results")
        return results

    async def _query_and_match(self, item: ResourceModel) -> RemoteResource | None:
        results = await self._query(item)
        return self._match_item(item, results) if results else None

    def _split_items(self, items: Iterable[Any]) -> tuple[list[Any], list[Any]]:
        valid = []
        invalid = []
        for item in items:
            invalid.append(item) if self._should_skip(item) else valid.append(item)

        return valid, invalid

    def _match_item[T: RemoteResource](self, item: HasMutableURI, results: MutableSequence[T]) -> T | None:
        match = self._pop_match_from_results(item, results)
        if match is not None:
            self._assign_attributes_from_match(item, match)
        return match

    def _pop_match_from_results[T: HasURI](self, item: HasMutableURI, results: MutableSequence[T]) -> T | None:
        if not results:
            return

        match = self.matcher.match(item, results) if self.matcher is not None else results[0]
        if match is None:
            self._log_debug(item, message="No match found")
            return

        results.remove(match)

        message = f"Match found: {self._get_item_log_name(match)}"
        if match.has_uri:
            message += f" - {match.uri}"
        self._log_debug(item, message=message)

        return match

    def _assign_attributes_from_match(self, item: HasMutableURI, match: HasURI) -> None:
        if self.assign_uri:
            self._assign_uri_from_match(item, match)

    def _assign_uri_from_match(self, item: HasMutableURI, match: HasURI) -> None:
        if not isinstance(item, HasMutableURI) or not isinstance(match, HasURI) or not match.has_uri:
            return

        if item.uri != match.uri:
            self._log_debug(item, f"Setting URI: {match.uri}")
            item.uri = match.uri

    ###########################################################################
    ## Item validators
    ###########################################################################
    def _should_skip(self, item: Any) -> bool:
        if self.skip_if_has_uri and isinstance(item, HasURI) and item.has_uri:
            self._log_debug(item, message=f"Skipping: already has a URI")
            return True
        return False

    def _should_search_on_items_only(self, item: CollectionModel) -> bool:
        message = "Searching as items only"
        if self.items_only_on_collections:
            reason = "set to search for collections as items only"
            self._log_debug(item, message=f"{message}: {reason}")
            return True

        match item:
            case AlbumCollection() as coll if self.compilation_albums_as_tracks_only and coll.compilation:
                reason = "is compilation album + set to search for compilation albums as tracks only"
                self._log_debug(item, message=f"{message}: {reason}")
                return True
            case _ if not isinstance(item, ResourceModel):
                self._log_debug(item, message=f"{message}: not a resource which can be searched for directly")
                return True

        return False

    ###########################################################################
    ## Logging
    ###########################################################################
    def log_results(self, results: Sequence[tuple[str, SearchResult]]) -> None:
        """Log the given search results"""
        header = f"{self.source.upper()} SEARCH RESULTS"
        table = SearchResult.generate_table(results=results, header=header)

        self._logger.report(table, new_line_start=True, new_line_end=True)

    def _log_start(self, items: Collection, default_type: str) -> None:
        types = self._logger.format_types_to_string(items) or default_type
        message = f"Searching for matches on {self.source} for {len(items)} {types}"
        self._logger.info(message, header=1)

    def _log_skip(self, message: str) -> None:
        self._logger.extra(colored(message, "yellow"))

    def _log_debug(self, item: Any, message: str) -> None:
        name = self._get_item_log_name(item)
        name = truncate_string(name, 30)
        self._logger.debug(f"{name} | {message}")

    @staticmethod
    def _get_item_log_name(item: Any) -> str:
        match item:
            case IsFile() as it if it.filename is not None:
                return str(it.filename)
            case IsLocalFile() as it if it.path is not None:
                return str(it.path)
            case HasName() as it if it.name is not None:
                return it.name
            case HasURI() as it if it.has_uri:
                return str(it.uri)

        return str(id(item))
