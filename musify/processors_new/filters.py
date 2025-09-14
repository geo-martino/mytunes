from abc import ABCMeta, abstractmethod
from collections.abc import Collection, Iterator
from pathlib import Path
from typing import Any, Annotated

from pydantic import Field, field_validator, BeforeValidator

from musify._types import StrippedString, to_set
from musify.exception import MusifyTypeError
from musify.models.properties.file import _IsFile, PathMapper, PathInputType
from musify.processors_new._base import Processor


class Filter[T](Processor, metaclass=ABCMeta):
    """Base class for all filters."""

    @property
    @abstractmethod
    def ready(self) -> bool:
        """Indicates if the filter is set and ready to be used."""
        raise NotImplementedError

    @abstractmethod
    def check(self, item: T) -> bool:
        """
        Check if the filter applies to the given item.

        :param item: The item to check against the filter.
        :return: A boolean indicating if the item matches the filter.
        """
        raise NotImplementedError

    def apply(self, items: Collection[T]) -> list[T]:
        """
        Apply the filter to the given items.

        :param items: The items to filter.
        :return: A sequence of items that match the filter.
        """
        return list(filter(self.check, items))


class FilterComposite[T](Filter[T], Collection[Filter[T]], metaclass=ABCMeta):
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
            if isinstance(filter_, FilterComposite):
                return iter(filter_)
            return iter((filter_,))

        return (f for filter_ in self.filters for f in flatten_filters(filter_))

    def __len__(self):
        return len(self.filters)

    def __contains__(self, item: Any):
        return item in self.filters


class FilterValues[T](Filter[T]):
    """Filter based on a defined list of values."""
    values: Annotated[set[T], BeforeValidator(to_set)] = Field(
        description="Set of values to filter against",
        default_factory=set,
    )

    @property
    def ready(self) -> bool:
        return len(self.values) > 0

    def check(self, item: T) -> bool:
        return not self.ready or item in self.values

    def __iter__(self):
        return iter(self.values)

    def __len__(self):
        return len(self.values)

    def __contains__(self, item: Any):
        return item in self.values

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, self.__class__) and self.values == other.values


class FilterPaths(FilterValues[str]):
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

    def check(self, item: PathInputType) -> bool:
        if not isinstance(item, str | Path | _IsFile):
            raise MusifyTypeError(f"Unrecognised type for path filtering: {type(item)}")

        return not self.ready or self.path_mapper.map(item, check_existence=False) in self.values


class FilterIncludeExclude[T, IF: Filter, EF: Filter](FilterComposite[T]):
    include: IF = Field(
        description="Filter for items to include",
        default_factory=FilterValues,
    )
    exclude: EF = Field(
        description="Filter for items to exclude",
        default_factory=FilterValues,
    )

    @property
    def filters(self) -> Collection[Filter]:
        return self.include, self.exclude

    def check(self, item: T) -> bool:
        return not self.ready or (self.include.check(item) and not self.exclude.check(item))

    def __eq__(self, item: Any):
        return isinstance(item, self.__class__) and all((
            self.include == item.include,
            self.exclude == item.exclude
        ))
