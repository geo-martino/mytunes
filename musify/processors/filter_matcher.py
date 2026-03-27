"""
Processors that filter down objects and data types based on some given configuration.
"""
from __future__ import annotations

import logging
from collections.abc import Collection
from dataclasses import field, dataclass
from typing import Any

from musify.base import Result
from musify.field import TagField
from musify.logger import MusifyLogger
from musify.processors.base import Filter, FilterComposite
from musify.processors.filter import FilterComparers, FilterDefinedList


@dataclass(frozen=True)
class MatchResult[T: Any](Result):
    """Results from :py:class:`FilterMatcher` separated by individual filter results."""
    #: Objects that matched include settings.
    included: Collection[T] = field(default=tuple())
    #: Objects that matched exclude settings.
    excluded: Collection[T] = field(default=tuple())
    #: Objects that matched :py:class:`Comparer` settings
    compared: Collection[T] = field(default=tuple())
    #: Objects that matched on any ``group_by`` settings
    grouped: Collection[T] = field(default=tuple())

    @property
    def combined(self) -> list[T]:
        """Combine the individual results to one combined list"""
        return [track for track in [*self.compared, *self.included, *self.grouped] if track not in self.excluded]


class FilterMatcher[T: Any, U: Filter, V: Filter, X: FilterComparers](FilterComposite[T]):
    """
    Get matches for items based on given filters.

    :param include: A Filter for simple include comparisons to use when matching.
    :param exclude: A Filter for simple exclude comparisons to use when matching.
    :param comparers: A Filter for fine-grained comparisons to use when matching.
        When not given or the given Filter is not ready,
        returns all given values on match unless include or exclude are defined and ready.
    :param group_by: Once all other filters are applied, also include all other items that match this tag type
        from the matched items for any remaining unmatched items.
    """

    __slots__ = ("logger", "include", "exclude", "comparers", "group_by")

    def __init__(
            self,
            include: U = FilterDefinedList(),
            exclude: V = FilterDefinedList(),
            comparers: X = FilterComparers(),
            group_by: TagField | None = None,
            *_,
            **__
    ):
        super().__init__(comparers, include, exclude)
        # noinspection PyTypeChecker
        #: The :py:class:`MusifyLogger` for this  object
        self.logger: MusifyLogger = logging.getLogger(__name__)

        #: The filter that, when processed, returns items to include
        self.include = include
        #: The filter that, when processed, returns items to exclude
        self.exclude = exclude
        #: The comparers to use when processing for this filter
        self.comparers = comparers
        #: Once all other filters are applied, also include all other items that match this tag type
        #: from the matched items for the remaining items given
        self.group_by = group_by

    def __call__(self, *args, **kwargs) -> list[T]:
        return self.process(*args, **kwargs)

    def process(self, values: Collection[T], reference: T | None = None, *_, **__) -> list[T]:
        """
        Return a new, filtered list of items from input ``values`` that match the stored filters.

        :param values: List of items to filter.
        :param reference: Optional reference track to use when filtering on
            comparers and the comparer has no expected value.
        :return: List of items that match the conditions.
        """
        return self.process_to_result(values=values, reference=reference).combined

    def process_to_result(self, values: Collection[T], reference: T | None = None, *_, **__) -> MatchResult:
        """Same as :py:meth:`process` but returns the results of each filter to a :py:class`MatchResult` object"""
        if len(values) == 0:  # skip match
            return MatchResult()

        included = self.include(values)
        excluded = self.exclude(values) if self.exclude.ready else ()
        tracks_reduced = {track for track in values if track not in included}
        compared = self.comparers(tracks_reduced, reference=reference) if self.comparers.ready else ()

        result = MatchResult(included=included, excluded=excluded, compared=compared)
        grouped = self._get_group_by_results(values, matched=result.combined)

        if not grouped:
            return result
        return MatchResult(included=included, excluded=excluded, compared=compared, grouped=grouped)

    def _get_group_by_results(self, values: Collection[T], matched: Collection[T]) -> tuple[T, ...]:
        if not self.group_by or len(values) == len(matched):
            return ()
        tag_names = self.group_by.to_tag()
        tag_values = {item[tag_name] for item in matched for tag_name in tag_names if hasattr(item, tag_name)}

        return tuple(
            item for item in values
            if item not in matched
            and any(item[tag_name] in tag_values for tag_name in tag_names if hasattr(item, tag_name))
        )

    def __eq__(self, item: Any):
        return isinstance(item, self.__class__) and all((
            self.comparers == item.comparers,
            self.include == item.include,
            self.exclude == item.exclude,
            self.group_by == item.group_by,
        ))

    def as_dict(self):
        return {
            "include": self.include,
            "exclude": self.exclude,
            "comparers": self.comparers,
            "group_by": self.group_by.name.lower() if self.group_by else None
        }
