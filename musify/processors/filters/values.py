from pathlib import Path
from typing import Annotated, Iterable, Mapping, Any, Iterator, Self

from pydantic import BeforeValidator, Field, model_validator, validate_call, field_validator

from musify._types import to_set, StrippedString
from musify.models import BaseModel
from musify.models.properties.file import PathMapper, IsLocalFile, PathInputType
from musify.processors.filters._base import Filter


class ValuesFilter[IT](Filter[IT]):
    """Filter based on a defined list of values."""
    values: Annotated[set[IT], BeforeValidator(to_set)] = Field(
        description="Set of values to filter against",
        default_factory=set,
    )

    @property
    def ready(self) -> bool:
        return len(self.values) > 0

    @model_validator(mode="before")
    @classmethod
    def _from_values[T: Iterable[T]](cls, values: T) -> T | dict[str, T]:
        if isinstance(values, (BaseModel, Mapping)) or not isinstance(values, Iterable):
            return values
        return {"values": values}

    @validate_call
    def check(self, item: IT, *_, **__) -> bool:
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

    @validate_call
    def check(self, item: PathInputType, *_, **__) -> bool:
        return self.path_mapper.unmap(item, check_existence=False) in self.values
