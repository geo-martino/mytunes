from abc import ABCMeta, abstractmethod
from collections.abc import Collection, Iterator, Mapping, Sequence, Iterable
from datetime import datetime
from pathlib import Path
from typing import Any, Annotated, Self, Literal

from pydantic import Field, field_validator, BeforeValidator, field_serializer, model_validator

from musify._types import StrippedString, to_set
from musify.exception import MusifyTypeError
from musify.models import MusifyResource
from musify.models.properties.file import IsLocalFile, PathMapper, PathInputType
from musify.processors_new._base import Processor, Result
from musify.processors_new.compare import Comparer


class Filter[T](Processor, metaclass=ABCMeta):
    """Base class for all filters."""

    @property
    @abstractmethod
    def ready(self) -> bool:
        """Indicates if the filter is set and ready to be used."""
        raise NotImplementedError

    @abstractmethod
    def check(self, item: T, *args, **kwargs) -> bool:
        """
        Check if the filter applies to the given item.

        :param item: The item to check against the filter.
        :return: A boolean indicating if the item matches the filter.
        """
        raise NotImplementedError

    def apply(self, items: Collection[T], *args, **kwargs) -> list[T]:
        """
        Apply the filter to the given items.

        :param items: The items to filter.
        :return: A sequence of items that match the filter.
        """
        if not self.ready:  # always return all items if filter is not setup
            print(datetime.now(), "MATCH NOT APPLYING", self)
            return list(items)

        def _filter(item: T) -> bool:
            return self.check(item, *args, **kwargs)
        print(datetime.now(), "MATCH APPLYING", self)
        return list(filter(_filter, items))


class CompositeFilter[T](Filter[T], Collection[Filter[T]], metaclass=ABCMeta):
    """Composite filter which filters based on many :py:class:`Filter` objects"""

    @property
    @abstractmethod
    def filters(self) -> Collection[Filter]:
        """All filters configured."""
        raise NotImplementedError

    @property
    def ready(self):
        return any(filter_.ready for filter_ in self.filters)

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


class ValuesFilter[T](Filter[T]):
    """Filter based on a defined list of values."""
    values: Annotated[set[T], BeforeValidator(to_set)] = Field(
        description="Set of values to filter against",
        default_factory=set,
    )

    @property
    def ready(self) -> bool:
        return len(self.values) > 0

    def check(self, item: T, *_, **__) -> bool:
        return item in self.values

    def __iter__(self):
        return iter(self.values)

    def __len__(self):
        return len(self.values)

    def __contains__(self, item: Any):
        return item in self.values

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, self.__class__) and self.values == other.values


class PathsFilter(ValuesFilter[str]):
    """Filter based on a defined list of values."""
    values: Annotated[set[StrippedString], BeforeValidator(to_set)] = Field(
        description="Set of paths to filter against. These will be stored as un-mapped paths if a PathMapper is set.",
        default_factory=set,
    )
    path_mapper: PathMapper = Field(
        description="Mapper to use to map paths.",
        default_factory=PathMapper,
    )

    @property
    def paths(self) -> set[Path]:
        """Get the values as Path objects."""
        paths = self.values
        if self.path_mapper is not None:
            paths = self.path_mapper.map_many(paths, check_existence=False)
        return set(map(Path, paths))

    @paths.setter
    def paths(self, value: set[Path]) -> None:
        self.values = set(map(str, value))

    @field_validator("values", mode="before", check_fields=True)
    @staticmethod
    def _extract_values_from_files(values: Iterable[Any]) -> Iterator[str]:
        return (str(value.path) if isinstance(value, IsLocalFile) else value for value in values)

    @field_validator("values", mode="before", check_fields=True)
    @staticmethod
    def _extract_values_from_paths(values: Iterable[Any]) -> Iterator[str]:
        return (str(value) if isinstance(value, Path) else value for value in values)

    @model_validator(mode="after")
    def _unmap_paths(self) -> Self:
        if self.path_mapper is None:
            return self

        values = set(self.path_mapper.unmap_many(self.values, check_existence=False))
        if values != self.values:
            self.values = values
        return self

    def check(self, item: PathInputType, *_, **__) -> bool:
        if not isinstance(item, str | Path | IsLocalFile):
            raise MusifyTypeError(f"Unrecognised type for path filtering: {type(item)}")

        return self.path_mapper.unmap(item, check_existence=False) in self.values


class IncludeExcludeFilter[T, IF: Filter, EF: Filter](CompositeFilter[T]):
    include: IF = Field(
        description="Filter for items to include",
        default_factory=ValuesFilter,
    )
    exclude: EF = Field(
        description="Filter for items to exclude",
        default_factory=ValuesFilter,
    )

    @property
    def filters(self) -> Collection[Filter]:
        return self.include, self.exclude

    def check(self, item: T, *_, **__) -> bool:
        match = self.include.check(item)
        if self.exclude.ready:
            match &= not self.exclude.check(item)
        return match

    def __eq__(self, item: Any):
        return isinstance(item, self.__class__) and all((
            self.include == item.include,
            self.exclude == item.exclude
        ))


class ComparerFilter[T: str | MusifyResource](Filter[T]):
    """Filter based on a defined map of :py:class:`Comparer` objects mapped to additional ."""
    comparers: Mapping[Comparer, tuple[bool, Self]] = Field(
        description=(
            "Comparers to filter against. Mapped to additional filters where the first boolean indicates "
            "whether to AND (True) or OR (False) the comparer and sub-filter results."
        ),
        default_factory=dict,
    )
    match_all: bool = Field(
        description="When true, all comparers must match, otherwise any can match",
        default=True,
    )

    @field_validator("comparers", mode="before", check_fields=True)
    @staticmethod
    def _comparer_to_mapping(
        value: Comparer | Iterable[Comparer] | Mapping[str, tuple[bool, Self]]
    ) -> Mapping[str, tuple[bool, Self]]:
        if isinstance(value, Comparer):
            value = [value]
        if not isinstance(value, Mapping):
            value = {comparer: (False, ComparerFilter()) for comparer in value}

        return value

    @field_serializer("comparers", check_fields=True)
    def _flatten_comparers[T: Mapping[Comparer, tuple]](self, comparers: T) -> T | list[Comparer]:
        if all(not sub_filter.ready for _, sub_filter in comparers.values()):
            return list(self.comparers.keys())
        return comparers

    @property
    def ready(self) -> bool:
        return len(self.comparers) > 0

    def check(self, item: T, reference: T | None = None, *_, **__) -> bool:
        # initial state determined by ready and match_all states
        matched = self.ready and self.match_all

        for comparer, (sub_combine, sub_filter) in self.comparers.items():
            cmp_match = comparer.compare(item, reference=reference)
            sub_match = sub_filter.check(item, reference=reference)

            combined_match = (cmp_match and sub_match) if sub_combine else (cmp_match or sub_match)
            matched = (matched and combined_match) if self.match_all else (matched or combined_match)

        return matched

    def __eq__(self, item: Any):
        return isinstance(item, self.__class__) and all((
            self.comparers == item.comparers,
            self.match_all == item.match_all
        ))


class MatchResult[T: Any](Result):
    """Results from :py:class:`MatchFilter` separated by individual filter results."""
    included: Sequence[T] = Field(
        description="Objects that matched include settings.",
        default_factory=tuple,
    )
    excluded: Sequence[T] = Field(
        description="Objects that matched exclude settings.",
        default_factory=tuple,
    )
    compared: Sequence[T] = Field(
        description="Objects that matched :py:class:`Comparer` settings",
        default_factory=tuple,
    )
    grouped: Sequence[T] = Field(
        description="Objects that matched on any ``group_by`` settings",
        default_factory=tuple,
    )

    @property
    def combined(self) -> list[T]:
        """Combine the individual results to one combined list"""
        return [track for track in [*self.compared, *self.included, *self.grouped] if track not in self.excluded]


class MatchFilter[T, IF: Filter, EF: Filter](IncludeExcludeFilter[T, IF, EF]):
    """
    Filter which matches based on include, exclude and comparer filters,
    with additional option for including a given tag grouping.
    """
    compare: ComparerFilter[T] = Field(
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

    def check(self, item: T, reference: T | None = None, *_, **__) -> bool:
        if self.exclude.check(item, reference=reference):
            return False

        match = self.include.check(item, reference=reference)
        if self.compare.ready:
            match |= self.compare.check(item, reference=reference)

        return match  # cannot apply group_by logic as it depends on the full set of values

    def apply(self, values: Collection[T], reference: T | None = None, *_, **__) -> list[T]:
        return self.match(values=values, reference=reference).combined

    def match(self, values: Collection[T], reference: T | None = None) -> MatchResult:
        """Same as :py:meth:`apply` but returns the results of each filter to a :py:class`MatchResult` object"""
        if len(values) == 0:
            return MatchResult()

        included = self.include.apply(values)
        excluded = self.exclude.apply(values) if self.exclude.ready else ()

        compared = ()
        if self.compare.ready:
            not_included = [item for item in values if item not in included]
            compared = self.compare.apply(not_included, reference=reference)

        combined = [track for track in [*compared, *included] if track not in excluded]
        grouped = self._match_on_group_by(values, matched=combined)

        return MatchResult(included=included, excluded=excluded, compared=compared, grouped=grouped)

    def _match_on_group_by(self, values: Collection[T], matched: Collection[T]) -> tuple[T, ...]:
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
