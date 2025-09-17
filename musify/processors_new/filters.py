from abc import ABCMeta, abstractmethod
from collections.abc import Collection, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any, Annotated, Self

from pydantic import Field, field_validator, BeforeValidator

from musify._types import StrippedString, to_set, to_tuple
from musify.exception import MusifyTypeError
from musify.models import MusifyResource
from musify.models.properties.file import _IsFile, PathMapper, PathInputType
from musify.processors_new._base import Processor
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
            return list(items)

        def _filter(item: T) -> bool:
            return self.check(item, *args, **kwargs)
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
    values: set[StrippedString] = Field(
        description="Set of paths to filter against",
        default_factory=set,
    )
    path_mapper: PathMapper = Field(
        description="Mapper to use when mapping string paths.",
        default_factory=PathMapper,
    )

    @property
    def paths(self) -> set[Path]:
        """Get the values as Path objects."""
        return set(map(Path, self.values))

    @field_validator("values", mode="before", check_fields=True)
    @staticmethod
    def _extract_values_from_files(values: Collection[Any]) -> Iterator[str]:
        return (str(value.path) if isinstance(value, _IsFile) else value for value in values)

    @field_validator("values", mode="before", check_fields=True)
    @staticmethod
    def _extract_values_from_paths(values: Collection[Any]) -> Iterator[str]:
        return (str(value) if isinstance(value, Path) else value for value in values)

    def check(self, item: PathInputType, *_, **__) -> bool:
        if not isinstance(item, str | Path | _IsFile):
            raise MusifyTypeError(f"Unrecognised type for path filtering: {type(item)}")

        return self.path_mapper.map(item, check_existence=False) in self.values


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
        return self.include.check(item) and not self.exclude.check(item)

    def __eq__(self, item: Any):
        return isinstance(item, self.__class__) and all((
            self.include == item.include,
            self.exclude == item.exclude
        ))


class ComparerFilter[T: str | MusifyResource](Filter[T]):
    comparers: Mapping[Comparer, tuple[bool, Self]] = Field(
        description="Comparers to filter against",
        default_factory=dict,
    )
    match_all: bool = Field(
        description="When true, all comparers must match, otherwise any can match",
        default=True,
    )

    @field_validator("comparers", mode="before", check_fields=True)
    @staticmethod
    def _comparer_to_mapping(value: Any) -> Any:
        if isinstance(value, Comparer):
            value = [value]
        if not isinstance(value, Mapping):
            value = {comparer: (False, ComparerFilter()) for comparer in value}

        return value

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
