from collections.abc import Collection
from typing import Any, Annotated

from pydantic import Field, computed_field, validate_call

from musify._types import StrippedString
from musify.models.result import Result, LenLogFormatter
from musify.processors.filters._base import Filter
from musify.processors.filters.compare import ComparerFilter
from musify.processors.filters.composite import IncludeExcludeFilter


class MatchResult[IT: Any](Result):
    """Results from :py:class:`MatchFilter` separated by individual filter results."""
    included: Annotated[
        tuple[IT, ...],
        LenLogFormatter(
            width=6, alignment="right", colour="blue", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LenLogFormatter(
            width=6, alignment="right", colour="green", colour_attributes=["bold"], condition=lambda x: x > 0
        ),
    ] = Field(
        description="Items that matched include settings.",
        default_factory=tuple,
    )
    excluded: Annotated[
        tuple[IT, ...],
        LenLogFormatter(
            width=6, alignment="right", colour="blue", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LenLogFormatter(
            width=6, alignment="right", colour="red", colour_attributes=["bold"], condition=lambda x: x > 0
        ),
    ] = Field(
        description="Items that matched exclude settings.",
        default_factory=tuple,
    )
    compared: Annotated[
        tuple[IT, ...],
        LenLogFormatter(
            width=6, alignment="right", colour="blue", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LenLogFormatter(
            width=6, alignment="right", colour="yellow", colour_attributes=["bold"], condition=lambda x: x > 0
        ),
    ] = Field(
        description="Items that matched comparer settings",
        default_factory=tuple,
    )
    grouped: Annotated[
        tuple[IT, ...],
        LenLogFormatter(
            width=6, alignment="right", colour="blue", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LenLogFormatter(
            width=6, alignment="right", colour="magenta", colour_attributes=["bold"], condition=lambda x: x > 0
        ),
    ] = Field(
        description="Items that matched on any 'group by' settings",
        default_factory=tuple,
    )

    @computed_field(
        description="The final combined results of the match",
        alias="final",
    )
    @property
    def combined(self) -> Annotated[
        list[IT],
        LenLogFormatter(width=6, alignment="right", colour="blue", colour_attributes=["bold"], condition=lambda x: x == 0),
        LenLogFormatter(width=6, alignment="right", colour="green", colour_attributes=["bold"], condition=lambda x: x > 0),
    ]:
        """Combine the individual results to one combined list"""
        return [track for track in [*self.compared, *self.included, *self.grouped] if track not in self.excluded]

    @property
    def lengths(self) -> dict[str, int]:
        """Get lengths of each individual result set."""
        return dict(map(lambda key: (key, len(getattr(self, key))), self.model_fields.keys()))


class MatchFilter[IT, IF: Filter, EF: Filter](IncludeExcludeFilter[IT, IF, EF]):
    """
    Filter which matches based on include, exclude and comparer filters,
    with additional option for including a given tag grouping.
    """
    compare: ComparerFilter[IT] = Field(
        description="Comparer filter to use when matching.",
        default_factory=ComparerFilter,
    )
    group_by: StrippedString | None = Field(
        description=(
            "Once all other filters are applied, also include all other items that match this tag type "
            "from the matched items for the remaining items given."
        ),
        default=None,
    )

    @validate_call
    def check(self, item: IT, reference: IT | None = None, *_, **__) -> bool:
        if self.exclude.check(item, reference=reference):
            return False

        match = self.include.check(item, reference=reference)
        if self.compare.ready:
            match |= self.compare.check(item, reference=reference)

        return match  # cannot apply group_by logic as it depends on the full set of values

    def apply(self, values: Collection[IT], reference: IT | None = None, *_, **__) -> list[T]:
        return self.match(values=values, reference=reference).combined

    def match(self, values: Collection[IT], reference: IT | None = None) -> MatchResult:
        """Same as :py:meth:`apply` but returns the results of each filter to a :py:class`MatchResult` object"""
        if len(values) == 0:
            return MatchResult()

        included = self.include.apply(values)
        excluded = self.exclude.apply(values) if self.exclude.ready else ()

        compared = ()
        if self.compare.ready:
            # use object id matching to filter out already included items
            # doing this because using Pydantic __contains__ comparison between models is too slow
            included_ids = {id(item) for item in included}
            not_included = [item for item in values if id(item) not in included_ids]
            compared = self.compare.apply(not_included, reference=reference)

        combined = [track for track in [*compared, *included] if track not in excluded]
        grouped = self._match_on_group_by(values, matched=combined)

        return MatchResult(included=included, excluded=excluded, compared=compared, grouped=grouped)

    def _match_on_group_by(self, values: Collection[IT], matched: Collection[IT]) -> tuple[IT, ...]:
        if not self.group_by or len(values) == len(matched):
            return ()

        tag_values = {
            getattr(item, self.group_by) for item in matched if getattr(item, self.group_by, None) is not None
        }

        return tuple(
            item for item in values
            if item not in matched and hasattr(item, self.group_by) and getattr(item, self.group_by) in tag_values
        )

    def __eq__(self, item: Any):
        return isinstance(item, self.__class__) and all((
            self.include == item.include,
            self.exclude == item.exclude,
            self.compare == item.compare,
            self.group_by == item.group_by,
        ))
