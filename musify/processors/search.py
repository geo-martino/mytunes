"""
Processor operations that search for and match given items with remote items.

Searches for matches on remote APIs, matches the item to the best matching result from the query,
and assigns the ID of the matched object back to the item.
"""
import logging
from collections.abc import Mapping, Sequence, Iterable, Collection, Awaitable
from dataclasses import dataclass, field
from typing import Any, Self

from aiorequestful.types import UnitIterable

from musify.base import MusifyObject, MusifyItemSettable, Result
from musify.exception import MusifyAttributeError
from musify.field import TagField, TagFields as Tag
from musify.libraries.core.collection import MusifyCollection
from musify.libraries.remote.core.api import RemoteAPI
from musify.libraries.remote.core.factory import RemoteObjectFactory
from musify.libraries.remote.core.types import RemoteObjectType
from musify.logger import MusifyLogger
from musify.logger import REPORT
from musify.processors.base import Processor
from musify.processors.match import ItemMatcher
from musify.utils import align_string, get_max_width


@dataclass(frozen=True)
class ItemSearchResult[T: MusifyItemSettable](Result):
    """Stores the results of the searching process."""
    #: Sequence of Items for which matches were found from the search.
    matched: Sequence[T] = field(default=tuple())
    #: Sequence of Items for which matches were not found from the search.
    unmatched: Sequence[T] = field(default=tuple())
    #: Sequence of Items which were skipped during the search.
    skipped: Sequence[T] = field(default=tuple())


@dataclass(frozen=True)
class SearchConfig:
    """Key settings related to a search algorithm."""
    #: The fields to match results on.
    match_fields: TagField | Iterable[TagField]
    #: A sequence of the tag names to use as search fields in the 1st pass.
    search_fields_1: Sequence[TagField] = (Tag.NAME,)
    #: If no results are found from the tag names in ``search_fields_1`` on the 1st pass,
    #: an optional sequence of the tag names to use as search fields in the 2nd pass.
    search_fields_2: Iterable[TagField] = ()
    #: If no results are found from the tag names in ``search_fields_2`` on the 2nd pass,
    #: an optional sequence of the tag names to use as search fields in the 3rd pass.
    search_fields_3: Iterable[TagField] = ()

    #: The number of the results to request when querying the API.
    result_count: int = 10
    #: The minimum acceptable score for an item to be considered a match.
    min_score: float = 0.1
    #: The maximum score for an item to be considered a perfect match.
    #: After this score is reached by an item, any other items are disregarded as potential matches.
    max_score: float = 0.8
    #: When True, items determined to be karaoke are allowed when matching added items.
    #: Skip karaoke results otherwise.
    allow_karaoke: bool = False


class RemoteItemSearcher(Processor):
    """
    Searches for remote matches for a list of item collections.

    :param matcher: The :py:class:`ItemMatcher` to use when comparing any changes made by the user in remote playlists
        during the checking operation
    :param object_factory: The :py:class:`RemoteObjectFactory` to use when creating new remote objects.
        This must have a :py:class:`RemoteAPI` assigned for this processor to work as expected.
    """

    __slots__ = ("logger", "matcher", "factory")

    #: The :py:class:`SearchSettings` for each :py:class:`RemoteObjectType`
    search_settings: dict[RemoteObjectType, SearchConfig] = {
        RemoteObjectType.TRACK: SearchConfig(
            match_fields={Tag.TITLE, Tag.ARTIST, Tag.ALBUM, Tag.LENGTH},
            search_fields_1=[Tag.NAME, Tag.ARTIST],
            search_fields_2=[Tag.NAME, Tag.ALBUM],
            search_fields_3=[Tag.NAME],
            result_count=10,
            min_score=0.1,
            max_score=0.8,
            allow_karaoke=False,
        ),
        RemoteObjectType.ALBUM: SearchConfig(
            match_fields={Tag.ARTIST, Tag.ALBUM, Tag.LENGTH},
            search_fields_1=[Tag.NAME, Tag.ARTIST],
            search_fields_2=[Tag.NAME],
            result_count=5,
            min_score=0.1,
            max_score=0.7,
            allow_karaoke=False,
        )
    }

    @property
    def api(self) -> RemoteAPI:
        """The :py:class:`RemoteAPI` to call"""
        return self.factory.api

    def __init__(self, matcher: ItemMatcher, object_factory: RemoteObjectFactory):
        # noinspection PyTypeChecker
        #: The :py:class:`MusifyLogger` for this  object
        self.logger: MusifyLogger = logging.getLogger(__name__)

        #: The :py:class:`ItemMatcher` to use when comparing any changes made by the user in remote playlists
        #: during the checking operation
        self.matcher = matcher
        #: The :py:class:`RemoteObjectFactory` to use when creating new remote objects.
        self.factory = object_factory

    async def __aenter__(self) -> Self:
        await self.api.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.api.__aexit__(exc_type, exc_val, exc_tb)

    async def _get_results(
            self, item: MusifyObject, kind: RemoteObjectType, settings: SearchConfig
    ) -> list[dict[str, Any]] | None:
        """Query the API to get results for the current item based on algorithm settings"""
        self.matcher.clean_tags(item)

        async def execute_query(keys: Iterable[TagField]) -> tuple[list[dict[str, Any]], str]:
            """Generate and execute the query against the API for the given item's cleaned ``keys``"""
            attributes = [item.clean_tags.get(key) for key in keys]
            q = " ".join(str(attr) for attr in attributes if attr)
            return await self.api.query(q, kind=kind, limit=settings.result_count), q

        results, query = await execute_query(settings.search_fields_1)
        if not results and settings.search_fields_2:
            results, query = await execute_query(settings.search_fields_2)
        if not results and settings.search_fields_3:
            results, query = await execute_query(settings.search_fields_3)

        if results:
            self.matcher.log([item.name, f"Query: {query}", f"{len(results)} results"])
            return results
        self.matcher.log([item.name, f"Query: {query}", "Match failed: No results."], pad="<")

    def _log_results(self, results: Mapping[str, ItemSearchResult]) -> None:
        """Logs the final results of the ItemSearcher"""
        if not results:
            return

        max_width = get_max_width(results)

        total_matched = 0
        total_unmatched = 0
        total_skipped = 0
        total_all = 0

        for name, result in results.items():
            matched = len(result.matched)
            unmatched = len(result.unmatched)
            skipped = len(result.skipped)
            total = matched + unmatched + skipped

            total_matched += matched
            total_unmatched += unmatched
            total_skipped += skipped
            total_all += total

            colour1 = "\33[92m" if matched > 0 else "\33[94m"
            colour2 = "\33[92m" if unmatched == 0 else "\33[91m"
            colour3 = "\33[92m" if skipped == 0 else "\33[93m"

            self.logger.report(
                f"\33[1m{align_string(name, max_width=max_width)} \33[0m|"
                f"{colour1}{matched:>6} matched \33[0m| "
                f"{colour2}{unmatched:>6} unmatched \33[0m| "
                f"{colour3}{skipped:>6} skipped \33[0m| "
                f"\33[97m{total:>6} total \33[0m"
            )

        self.logger.report(
            f"\33[1;96m{'TOTALS':<{max_width}} \33[0m|"
            f"\33[92m{total_matched:>6} matched \33[0m| "
            f"\33[91m{total_unmatched:>6} unmatched \33[0m| "
            f"\33[93m{total_skipped:>6} skipped \33[0m| "
            f"\33[97m{total_all:>6} total \33[0m"
        )
        self.logger.print_line(REPORT)

    @staticmethod
    def _determine_remote_object_type(obj: MusifyObject) -> RemoteObjectType:
        if hasattr(obj, "kind"):
            return obj.kind
        raise MusifyAttributeError(f"Given object does not specify a RemoteObjectType: {obj.__class__.__name__}")

    def __call__[T: MusifyItemSettable](
            self, collections: Collection[MusifyCollection[T]]
    ) -> Awaitable[dict[str, ItemSearchResult[T]]]:
        return self.search(collections)

    async def search[T: MusifyItemSettable](
            self, collections: Collection[MusifyCollection[T]]
    ) -> dict[str, ItemSearchResult[T]]:
        """
        Searches for remote matches for the given list of item collections.

        :return: Map of the collection's name to its :py:class:`ItemSearchResult` object.
        """
        self.logger.debug("Searching: START")
        if not [item for c in collections for item in c.items if item.has_uri is None]:
            self.logger.debug("\33[93mNo items to search. \33[0m")
            return {}

        kinds = {coll.__class__.__name__ for coll in collections}
        kind = kinds.pop() if len(kinds) == 1 else "collection"
        self.logger.info(
            f"\33[1;95m ->\33[1;97m "
            f"Searching for matches on {self.api.source} for {len(collections)} {kind}s\33[0m"
        )

        async def _get_result(coll: MusifyCollection[T]) -> tuple[str, ItemSearchResult]:
            return coll.name, await self._search_collection(coll)

        # WARNING: making this run asynchronously will break tqdm; bar will get stuck after 1-2 ticks
        bar = self.logger.get_synchronous_iterator(collections, desc="Searching",  unit=f"{kind}s")
        search_results = dict([await _get_result(coll) for coll in bar])

        self.logger.print_line()
        self._log_results(search_results)
        self.logger.debug("Searching: DONE\n")
        return search_results

    async def _search_collection[T: MusifyItemSettable](self, collection: MusifyCollection) -> ItemSearchResult[T]:
        kind = collection.__class__.__name__

        skipped = tuple(item for item in collection if item.has_uri is not None)
        if len(skipped) == len(collection):
            self.matcher.log([collection.name, "Skipping search, no items to search"], pad='<')

        if getattr(collection, "compilation", True) is False:
            self.matcher.log([collection.name, "Searching for collection as a unit"], pad='>')
            await self._search_collection_unit(collection=collection)

            missing = [item for item in collection.items if item.has_uri is None]
            if missing:
                self.matcher.log(
                    [collection.name, f"Searching for {len(missing)} unmatched items in this {kind}"]
                )
                await self._search_items(collection=collection)
        else:
            self.matcher.log([collection.name, "Searching for distinct items in collection"], pad='>')
            await self._search_items(collection=collection)

        return ItemSearchResult(
            matched=tuple(item for item in collection if item.has_uri and item not in skipped),
            unmatched=tuple(item for item in collection if item.has_uri is None and item not in skipped),
            skipped=skipped
        )

    async def _get_item_match[T: MusifyItemSettable](
            self, item: T, match_on: UnitIterable[TagField] | None = None, results: Iterable[T] = None
    ) -> tuple[T, T | None]:
        kind = self._determine_remote_object_type(item)
        search_config = self.search_settings[kind]

        if results is None:
            responses = await self._get_results(item, kind=kind, settings=search_config)
            # noinspection PyTypeChecker
            results: Iterable[T] = map(self.factory[kind], responses or ())

        result = self.matcher(
            item,
            results=results,
            match_on=match_on if match_on is not None else search_config.match_fields,
            min_score=search_config.min_score,
            max_score=search_config.max_score,
            allow_karaoke=search_config.allow_karaoke,
        ) if results else None

        return item, result

    async def _search_items[T: MusifyItemSettable](self, collection: Iterable[T], **kwargs) -> None:
        """
        Search for matches on individual items in an item collection that have ``None`` on ``has_uri`` attribute.
        kwargs are not required and are passed on to self._get_item_match.
        """
        async def _match(item: T) -> None:
            if item.has_uri is not None:
                return

            item, match = await self._get_item_match(item, **kwargs)
            if match and match.has_uri:
                item.uri = match.uri

        await self.logger.get_asynchronous_iterator(map(_match, collection), disable=True)

    async def _search_collection_unit[T: MusifyItemSettable](self, collection: MusifyCollection[T]) -> None:
        """
        Search for matches on an entire collection as a whole
        i.e. search for just the collection and not its distinct items.
        """
        if all(item.has_uri for item in collection):
            return

        kind = self._determine_remote_object_type(collection)
        search_config = self.search_settings[kind]

        responses = await self._get_results(collection, kind=kind, settings=search_config)
        key = self.api.collection_item_map[kind]
        await self.logger.get_asynchronous_iterator(
            (self.api.extend_items(response, kind=kind, key=key, leave_bar=False) for response in responses),
            disable=True
        )

        # noinspection PyProtectedMember,PyTypeChecker
        # order to prioritise results that are closer to the item count of the input collection
        results: list[T] = sorted(map(self.factory[kind], responses), key=lambda x: abs(x._total - len(collection)))

        result = self.matcher(
            collection,
            results=results,
            match_on=search_config.match_fields,
            min_score=search_config.min_score,
            max_score=search_config.max_score,
            allow_karaoke=search_config.allow_karaoke,
        )

        if not result:
            return

        # check all items in the collection have been matched
        # get matches on those that are still missing matches
        await self._search_items(collection, match_on=[Tag.TITLE], results=result.items)

    def as_dict(self) -> dict[str, Any]:
        return {
            "matcher": self.matcher,
            "remote_source": self.factory.api.source,
        }
