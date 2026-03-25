import textwrap
from collections.abc import Sequence, MutableSequence, Collection, Mapping, Iterable
from typing import Self, Any, Annotated

from pydantic import Field, validate_call, model_validator, field_validator
from termcolor import colored

from musify.models import ResourceModel
from musify.models.api import RemoteAPI, HasAPI
from musify.models.api.search import HasSearchEndpoints
from musify.models.collection import CollectionModel, RemoteCollection
from musify.models.collection.album import AlbumCollection
from musify.models.exception import MusifyValidationError
from musify.models.properties.file import IsFile, IsLocalFile
from musify.models.properties.logger import HasLogger
from musify.models.properties.name import HasName
from musify.models.properties.uri import HasImmutableURI, HasMutableURI, item_has_uri
from musify.models.remote import RemoteResource
from musify.models.result import TotalCountResult, LenLogFormatter
from musify.processors_new import Processor
from musify.processors_new.match import Matcher


class SearchResult[T: Any](TotalCountResult):
    """Stores the results of the searching process."""
    matches: Annotated[
        tuple[T, ...],
        LenLogFormatter(condition=lambda x: False),  # never log this attribute
    ] = Field(
        description=(
            "The matches from the API that were found in the search. This will match the items in the `matched` "
            "attribute so that the corresponding items can be easily mapped together."
        ),
        default_factory=tuple
    )
    matched: Annotated[
        tuple[T, ...],
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
        tuple[T, ...],
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
        tuple[T, ...],
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
            raise MusifyValidationError("The number of matches must be equal to the number of matched items.")
        return self


type _ApiT = RemoteAPI | HasSearchEndpoints


class Searcher[API: _ApiT](Processor, HasAPI):
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
            raise MusifyValidationError(f"API must be an instance of RemoteAPI, got {type(api)}")
        if not isinstance(api, HasSearchEndpoints):
            raise MusifyValidationError(f"API does not support search endpoints")

        return api

    @property
    def source(self) -> str:
        """The name of the remote service that this searcher is running on."""
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
        return await self._query_and_match(item)

    @validate_call
    async def search_items[T: ResourceModel](self, items: Sequence[T]) -> SearchResult[T]:
        """Search for matches for the given items and return the results."""
        if len(items) == 0:
            self._log_skip("No items to search.")
            return SearchResult()

        self._log_start(items, default_type="items")
        return await self._search_items(items, show_bar=True)

    async def _search_items[T: ResourceModel](self, items: Iterable[T], show_bar: bool = True) -> SearchResult[T]:
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
        if len(collections) == 0 or sum(collection.count for collection in collections) == 0:
            self._log_skip("No collections or items to search.")
            return {}

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

        match = await self._query_and_match(collection)
        match = await self._extend_collection_items(match)
        if match is None or not isinstance(match, CollectionModel):
            return name, await self._search_items(collection.iter_items, show_bar=show_bar)

        items, skipped = self._split_items(collection.iter_items)
        result = self._match_items(items, list(match.iter_items), skipped)
        if self.keep_matching_collection_items and result.unmatched:
            result = await self._search_from_result(result, items)

        return name, result

    async def _search_from_result[T: ResourceModel](self, result: SearchResult[T], items: Iterable[T]) -> SearchResult[T]:
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

        unit = self._get_unit(items, default_type="items")
        await self.logger.get_asynchronous_iterator(
            map(_search_and_match_item, result.unmatched),
            desc="Searching",
            unit=unit,
            initial=0,
            total=len(result.unmatched),
        )

        return SearchResult(matches=matches, matched=matched, unmatched=unmatched, skipped=result.skipped)

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

    async def _query_and_match(self, item: ResourceModel) -> RemoteResource | None:
        results = await self._query(item)
        return self._match_item(item, results) if results else None

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
    def log_results(self, results: Mapping[str, SearchResult]) -> None:
        """Log the given search results"""
        header = f"{self.source.upper()} SEARCH RESULTS"
        table = SearchResult.generate_table(results=results, header=header)
        self.logger.report(table)

    def _log_start(self, items: Collection, default_type: str) -> None:
        types = {f"{it.type.rstrip("s")}s" for it in items if isinstance(it, ResourceModel)}
        log_type = ", ".join(sorted(types)) if types else default_type
        message = f"Searching for matches on {self.source} for {len(items)} {log_type}"
        self.logger.info(message, header=1)

    def _log_skip(self, message: str) -> None:
        self.logger.extra(colored(message, "yellow"))

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
