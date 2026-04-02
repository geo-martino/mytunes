from abc import abstractmethod
from collections.abc import Collection, Iterator
from typing import Any, final, Annotated

from pydantic import Field, validate_call, computed_field

from musify._types import StrippedString
from musify.models.result import CountResult, LenLogFormatter, LogPosition
from musify.processors.filters import Filter
from musify.processors.filters._base import Filter
from musify.processors.filters.compare import ComparerFilter


# noinspection PyAbstractClass
class CompositeResult[IT: Any](CountResult):
    """Results from a :py:class:`CompositeFilter` operation separated by individual filter results."""
    @computed_field(
        description="The final combined items of the match",
        alias="final",
    )
    @property
    def combined(self) -> Annotated[
        list[IT],
        LogPosition(position=10),
        LenLogFormatter(
            width=6, alignment="right", colour="blue", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LenLogFormatter(
            width=6, alignment="right", colour="green", colour_attributes=["bold"], condition=lambda x: x > 0
        ),
    ]:
        """Combine the individual results to one combined list"""
        return self._combined

    @property
    @abstractmethod
    def _combined(self) -> list[IT]:
        raise NotImplementedError


class CompositeFilter[IT](Filter[IT], Collection[Filter[IT]]):
    """Composite filter which filters based on many :py:class:`Filter` objects"""

    @property
    @abstractmethod
    def filters(self) -> Collection[Filter]:
        """All filters configured."""
        raise NotImplementedError

    @property
    def ready(self):
        return any(filter_.ready for filter_ in self.filters)

    def apply(self, values: Collection[IT], reference: IT | None = None, *_, **__) -> list[T]:
        return self.match(values=values, reference=reference).combined

    @abstractmethod
    def match(self, values: Collection[IT], reference: IT | None = None) -> CompositeResult[IT]:
        """Same as :py:meth:`apply` but returns the results of each filter to a :py:class`FilterResult` object"""
        raise NotImplementedError

    def __iter__(self) -> Iterator[Filter]:
        def flatten_filters(filter_: Filter | Collection[Filter]) -> Iterator[Filter]:
            """
            Get flat iterator for all :py:class:`Filter` objects in the given Filter,
            flattening out any :py:class:`FilterComposite` objects
            """
            if isinstance(filter_, CompositeFilter):
                return iter(filter_)
            return iter((filter_,))

        return (f for filter_ in self.filters for f in flatten_filters(filter_))

    def __len__(self):
        return len(self.filters)

    def __contains__(self, item: Any):
        return item in self.filters


class IncludeExcludeResult[IT: Any](CompositeResult[IT]):
    included: Annotated[
        tuple[IT, ...],
        LogPosition(position=1),
        LenLogFormatter(
            width=6, alignment="right", colour="blue", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LenLogFormatter(
            width=6, alignment="right", colour="green", colour_attributes=["bold"], condition=lambda x: x > 0
        ),
    ] = Field(
        description="The items that matched include settings.",
        default_factory=tuple,
    )
    excluded: Annotated[
        tuple[IT, ...],
        LogPosition(position=2),
        LenLogFormatter(
            width=6, alignment="right", colour="blue", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LenLogFormatter(
            width=6, alignment="right", colour="red", colour_attributes=["bold"], condition=lambda x: x > 0
        ),
    ] = Field(
        description="The items that matched exclude settings.",
        default_factory=tuple,
    )

    @property
    def _combined(self) -> list[IT]:
        return [it for it in self.included if it not in self.excluded]


@final
class IncludeExcludeFilter[IT, IF: Filter, EF: Filter](CompositeFilter[IT]):
    __final__ = True

    include: IF = Field(
        description="Filter for items to include",
        default=(),
    )
    exclude: EF = Field(
        description="Filter for items to exclude",
        default=(),
    )

    @property
    def filters(self) -> Collection[Filter]:
        return self.include, self.exclude

    @validate_call
    def check(self, item: IT, *_, **__) -> bool:
        match = self.include.check(item)
        if self.exclude.ready:
            match &= not self.exclude.check(item)
        return match

    def apply(self, values: Collection[IT], reference: IT | None = None, *_, **__) -> list[T]:
        return self.match(values=values, reference=reference).combined

    def match(self, values: Collection[IT], reference: IT | None = None) -> IncludeExcludeResult[IT]:
        """Same as :py:meth:`apply` but returns the results of each filter to a :py:class`MatchResult` object"""
        if len(values) == 0:
            return IncludeExcludeResult()

        included = tuple(self.include.apply(values))
        excluded = self.exclude.apply(values) if self.exclude.ready else ()

        return IncludeExcludeResult(included=included, excluded=excluded)

    def __eq__(self, item: Any):
        return isinstance(item, self.__class__) and all((
            self.include == item.include,
            self.exclude == item.exclude
        ))


class GroupResult[IT: Any](IncludeExcludeResult[IT]):
    compared: Annotated[
        tuple[IT, ...],
        LogPosition(position=5),
        LenLogFormatter(
            width=6, alignment="right", colour="blue", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LenLogFormatter(
            width=6, alignment="right", colour="yellow", colour_attributes=["bold"], condition=lambda x: x > 0
        ),
    ] = Field(
        description="The items that matched comparer settings",
        default_factory=tuple,
    )
    grouped: Annotated[
        tuple[IT, ...],
        LogPosition(position=6),
        LenLogFormatter(
            width=6, alignment="right", colour="blue", colour_attributes=["bold"], condition=lambda x: x == 0
        ),
        LenLogFormatter(
            width=6, alignment="right", colour="magenta", colour_attributes=["bold"], condition=lambda x: x > 0
        ),
    ] = Field(
        description="The items that matched on 'group by' settings",
        default_factory=tuple,
    )

    @property
    def _combined(self) -> list[IT]:
        return [track for track in [*self.compared, *self.included, *self.grouped] if track not in self.excluded]


# noinspection PyFinal
@final
class GroupFilter[IT, IF: Filter, EF: Filter](IncludeExcludeFilter[IT, IF, EF]):
    """
    Filter which matches based on include, exclude and comparer filters,
    with additional option for including a given tag grouping.
    """
    __final__ = True

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

    def match(self, values: Collection[IT], reference: IT | None = None) -> GroupResult:
        """Same as :py:meth:`apply` but returns the results of each filter to a :py:class`MatchResult` object"""
        if len(values) == 0:
            return GroupResult()

        included = tuple(self.include.apply(values))
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

        return GroupResult(included=included, excluded=excluded, compared=compared, grouped=grouped)

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
