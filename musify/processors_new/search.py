import textwrap
from collections.abc import Sequence, MutableSequence, Collection, Mapping, Iterable
from typing import Self, Any

from pydantic import Field, validate_call, model_validator, field_validator
from termcolor import colored

from musify.exception import MusifyValueError
from musify.models import ResourceModel
from musify.models.api import RemoteAPI
from musify.models.api.search import HasSearchEndpoints
from musify.models.collection import CollectionModel, RemoteCollection
from musify.models.collection.album import AlbumCollection
from musify.models.properties.file import IsFile, IsLocalFile
from musify.models.properties.logger import HasLogger
from musify.models.properties.name import HasName
from musify.models.properties.uri import HasImmutableURI, HasMutableURI, item_has_uri
from musify.models.remote import RemoteResource
from musify.models.result import Result
from musify.processors_new import Processor
from musify.processors_new.match import Matcher


class SearchResult[T: ResourceModel](Result):
    """Stores the results of the searching process."""
    matches: tuple[T, ...] = Field(
        description=(
            "The matches from the API that were found in the search. This will match the items in the `matched` "
            "attribute so that the corresponding items can be easily mapped together."
        ),
        default_factory=tuple
    )
    matched: tuple[T, ...] = Field(
        description=(
            "The given items which were matched during the search. This will match the items in the `matches` "
            "attribute so that the corresponding items can be easily mapped together."
        ),
        default_factory=tuple
    )
    unmatched: tuple[T, ...] = Field(
        description="The items for which matches were not found from the search.",
        default_factory=tuple
    )
    skipped: tuple[T, ...] = Field(
        description="The items which were skipped during the search.",
        default_factory=tuple
    )

    @model_validator(mode="after")
    def _validate_matches_are_equal(self) -> Self:
        if len(self.matches) != len(self.matched):
            raise MusifyValueError("The number of matches must be equal to the number of matched items.")
        return self

    def generate_log(self, name: str) -> tuple[str, ...]:
        """Generate a log of stats for this result"""
        matched = len(self.matches)
        unmatched = len(self.unmatched)
        skipped = len(self.skipped)

        header = textwrap.shorten(name, 30, placeholder="...")
        row = (
            colored(header, "cyan", attrs=["bold"]),
            colored(f"{matched:>6} matched", "green" if matched > 0 else "blue"),
            colored(f"{unmatched:>6} unmatched", "green" if unmatched == 0 else "red"),
            colored(f"{skipped:>6} skipped", "green" if skipped == 0 else "yellow"),
            colored(f"{matched + unmatched + skipped:>6} total", "white"),
        )

        return row

    @staticmethod
    def generate_totals_log(results: Iterable[SearchResult]) -> tuple[str, ...]:
        """Generate a log of total stats for multiple results"""
        matched = sum(len(result.matches) for result in results)
        unmatched = sum(len(result.unmatched) for result in results)
        skipped = sum(len(result.skipped) for result in results)

        row = (
            colored("TOTALS", "white", attrs=["bold"]),
            colored(f"{matched:>6} matched", "green" if matched > 0 else "blue"),
            colored(f"{unmatched:>6} unmatched", "green" if unmatched == 0 else "red"),
            colored(f"{skipped:>6} skipped", "green" if skipped == 0 else "yellow"),
        )

        return row


class Searcher[API: RemoteAPI](Processor, HasLogger):
    api: API | HasSearchEndpoints = Field(
        description="The API to use for searching for matches.",
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

    compilation_albums_as_tracks_only: bool = Field(
        description=(
            "Whether to search for compilation albums as albums and match tracks to the matched album "
            "or to just search for the individual tracks instead."
        ),
        default=True,
    )

    @field_validator("api", mode="after", check_fields=True)
    @classmethod
    def _api_has_necessary_endpoints(cls, api: API | HasSearchEndpoints) -> API | HasSearchEndpoints:
        if not isinstance(api, RemoteAPI):
            raise MusifyValueError("API object must be an instance of RemoteAPI")
        if not isinstance(api, HasSearchEndpoints):
            raise MusifyValueError("API object must have search endpoints")
        return api

    @property
    def source(self) -> str:
        """The name of the source that this searcher is searching on, derived from the API's source."""
        return self.api.source.title()

    async def __aenter__(self) -> Self:
        await self.api.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.api.__aexit__(exc_type, exc_val, exc_tb)

    ###########################################################################
    ## Search: items
    ###########################################################################
    @validate_call
    async def search_item[T: ResourceModel](self, item: T) -> T | None:
        """Search for matches for the given item and return the matching result if found"""
        self._log_start([item], default_type="item")
        results = await self._query(item)
        return self._match_item(item, results)

    @validate_call
    async def search_items[T: ResourceModel](self, items: Sequence[T]) -> SearchResult[T]:
        """Search for matches for the given items and return the results."""
        self._log_start(items, default_type="items")
        return await self._search_items(items, show_bar=True)

    async def _search_items[T: ResourceModel](self, items: Iterable[T], show_bar: bool = True) -> SearchResult[T]:
        matches = []
        matched = []
        unmatched = []

        async def _search_and_match_item(item: T) -> None:
            results = await self._query(item)
            match = self._match_item(item, results)
            if match is not None:
                matched.append(item)
                matches.append(match)
            else:
                unmatched.append(item)

        items, skipped = self._split_items(items)
        unit = self._get_unit(items, default_type="items")
        await self.logger.get_asynchronous_iterator(
            map(_search_and_match_item, items),
            desc="Searching",
            unit=unit,
            initial=0,
            total=len(items),
            disable=not show_bar,
        )

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
    async def search_collection[T: ResourceModel](self, collection: CollectionModel) -> SearchResult[T]:
        """Search for matches for the given collection and return the results."""
        self._log_start([collection], default_type="collection")
        _, result = await self._search_collection(collection, show_bar=True)
        return result

    @validate_call
    async def search_collections[T: ResourceModel](
            self, collections: Sequence[CollectionModel]
    ) -> dict[str, SearchResult[T]]:
        """Search for matches for the given collection and return the results per collection."""
        self._log_start(collections, default_type="collections")

        async def _search_collection(collection: CollectionModel[T]) -> tuple[str, SearchResult[T]]:
            return await self._search_collection(collection, show_bar=False)

        unit = self._get_unit(collections, default_type="collections")
        bar = self.logger.get_asynchronous_iterator(
            map(_search_collection, collections),
            desc="Searching",
            unit=unit,
            initial=0,
            total=len(collections),
        )
        return dict(await bar)

    async def _search_collection[T: ResourceModel](
            self, collection: CollectionModel[T], show_bar: bool = True
    ) -> tuple[str, SearchResult[T]]:
        name = collection.name if isinstance(collection, HasName) else str(id(collection))

        if self._should_search_on_items_only(collection):
            return name, await self._search_items(collection.iter_items, show_bar=show_bar)
        collection: ResourceModel | CollectionModel  # type checked in the above condition

        results = await self._query(collection)
        match = self._match_item(collection, results)
        match = await self._extend_collection_items(match)
        if match is None or not isinstance(match, CollectionModel):
            return name, await self._search_items(collection.iter_items, show_bar=show_bar)

        items, skipped = self._split_items(collection.iter_items)
        return name, self._match_items(items, list(match.iter_items), skipped)

    async def _extend_collection_items[T: RemoteResource | RemoteCollection](self, collection: T) -> T:
        message = "Cannot extend items in collection: valid endpoints not configured for this resource type"
        if not isinstance(collection, RemoteCollection):
            try:
                collection = await collection.reload(self.api)
            except AttributeError:
                self._log_debug(collection, message=message)
                return collection

            if not isinstance(collection, RemoteCollection):
                message = "API did not return a collection when trying to extend items in collection"
                self._log_debug(collection, message=message)
                return collection

        try:
            await collection.extend(self.api)
        except AttributeError:
            self._log_debug(collection, message=message)

        return collection

    ###########################################################################
    ## Query and match utilities
    ###########################################################################
    async def _query(self, item: ResourceModel) -> list[RemoteResource] | None:
        if self._should_skip(item):
            return

        results = await self.api.search.query_item(item)
        if not results:
            self._log_debug(item, message="No results found")
            return None

        self._log_debug(item, message=f"Found {len(results)} results")
        return results

    def _split_items(self, items: Iterable[Any]) -> tuple[list[Any], list[Any]]:
        valid = []
        invalid = []
        for item in items:
            invalid.append(item) if self._should_skip(item) else valid.append(item)

        return valid, invalid

    def _match_item[T: RemoteResource](self, item: ResourceModel, results: MutableSequence[T]) -> T | None:
        match = self._pop_match_from_results(item, results)
        if match is not None:
            self._assign_attributes_from_match(item, match)
        return match

    def _pop_match_from_results[T](self, item: T, results: MutableSequence[T]) -> T | None:
        if not results:
            return

        match = self.matcher.match(item, results) if self.matcher is not None else results[0]
        if match is None:
            self._log_debug(item, message="No match found")
            return

        results.remove(match)

        message = f"Match found: {self._get_item_log_name(match)}"
        if item_has_uri(match):
            message += f" - {match.uri}"
        self._log_debug(item, message=message)

        return match

    def _assign_attributes_from_match[T: ResourceModel](self, item: T, match: T) -> None:
        if self.assign_uri:
            self._assign_uri_from_match(item, match)

    def _assign_uri_from_match[T: ResourceModel](self, item: T, match: T) -> None:
        if not isinstance(item, (HasImmutableURI, HasMutableURI)):
            return
        if not isinstance(match, (HasImmutableURI, HasMutableURI)) or not item_has_uri(match):
            return

        if item.uri != match.uri:
            self._log_debug(item, f"Setting URI: {match.uri}")
            item.uri = match.uri

    ###########################################################################
    ## Item validators
    ###########################################################################
    def _should_skip(self, item: Any) -> bool:
        if self.skip_if_has_uri and item_has_uri(item):
            self._log_debug(item, message=f"Skipping: already has a URI")
            return True
        return False

    def _should_search_on_items_only(self, item: CollectionModel) -> bool:
        message = "Searching as items only"
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
    def log_results(self, results: Mapping[str, SearchResult], skip_log: bool = False) -> list[tuple[str, ...]]:
        """Log stats on the given search results"""
        rows = [result.generate_log(name) for name, result in results.items()]
        rows.append(SearchResult.generate_totals_log(results.values()))

        if not skip_log:
            table = self._generate_table(rows)
            self.logger.report(table)

        return rows

    def _log_start(self, items: Collection, default_type: str) -> None:
        types = {f"{it.type.rstrip("s")}s" for it in items if isinstance(it, ResourceModel)}
        log_type = ", ".join(sorted(types)) if types else default_type
        message = f"Searching for matches on {self.source} for {len(items)} {log_type}"
        self.logger.info(message, header=1)

    def _log_debug(self, item: Any, message: str) -> None:
        name = self._get_item_log_name(item)
        name = textwrap.shorten(name, 30, placeholder="...")
        self.logger.debug(f"{name} | {message}")

    @staticmethod
    def _get_unit(items: Iterable, default_type: str) -> str:
        unit = default_type
        types = {it.type for it in items if isinstance(it, ResourceModel)}
        if len(types) == 1:
            unit = types.pop()

        return unit

    @staticmethod
    def _get_item_log_name(item: Any) -> str:
        match item:
            case IsFile() as file if file.filename is not None:
                return str(file.filename)
            case IsLocalFile() as file if file.path is not None:
                return str(file.path)
            case HasName() as named if named.name is not None:
                return named.name
            case HasMutableURI() | HasImmutableURI() as uri if item_has_uri(uri):
                return str(uri.uri)

        return str(id(item))
