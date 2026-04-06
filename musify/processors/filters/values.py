from pathlib import Path
from collections.abc import Iterable, Iterator, Mapping
from typing import Annotated, Any, Self, final

from pydantic import BeforeValidator, Field, model_validator, validate_call, field_validator

from musify._types import TO_SET, StrippedString, DEFAULT_IF_NONE
from musify.exception import MusifyTypeError
from musify.models import BaseModel
from musify.models.properties.file import PathMapper, IsLocalFile, PathInputType
from musify.models.properties.name import HasName
from musify.processors.filters._base import Filter


class ValueFilter[IT](Filter[IT]):
    """Filter based on a defined list of values."""
    values: Annotated[set[IT], TO_SET] = Field(
        description="Set of values to filter against",
        default_factory=set,
    )

    @property
    def ready(self) -> bool:
        return len(self.values) > 0

    @model_validator(mode="before")
    @classmethod
    def _from_values[T: Iterable[T]](cls, values: T) -> T | dict[str, T]:
        if isinstance(values, BaseModel):
            return values.model_dump()
        if isinstance(values, Mapping) or not isinstance(values, Iterable):
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
        return isinstance(other, type(self)) and self.values == other.values


@final
class NameFilter(ValueFilter[str]):
    """Filter based on a defined list of name values."""
    __final__ = True

    values: Annotated[set[StrippedString], TO_SET] = Field(
        description="Set of names to filter against.",
        default_factory=set,
    )

    @field_validator("values", mode="before", check_fields=True)
    @classmethod
    def _extract_values_from_models(cls, values: Iterable[Any]) -> Iterator[str]:
        return set(map(cls._extract_value_from_model, values))

    @staticmethod
    def _extract_value_from_model(item: Any) -> str:
        match item:
            case str():
                return item
            case HasName() if item.name is not None:
                return item.name
            case _:
                return item

    @validate_call
    def check(self, item: str | HasName, *_, **__) -> bool:
        return self._extract_value_from_model(item) in self.values


@final
class PathFilter(ValueFilter[str]):
    """Filter based on a defined list of path values."""
    __final__ = True

    values: Annotated[set[StrippedString], TO_SET] = Field(
        description="Set of paths to filter against. These will be stored as un-mapped paths if a PathMapper is set.",
        default_factory=set,
    )
    path_mapper: Annotated[PathMapper, DEFAULT_IF_NONE] = Field(
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

    @property
    def paths_valid(self) -> set[Path]:
        """Get the values as Path objects, only returning those that exist."""
        paths = self.values
        if self.path_mapper is not None:
            paths = filter(None, self.path_mapper.map_many(paths, check_existence=True))
        return set(map(Path, paths))

    @field_validator("values", mode="before", check_fields=True)
    @staticmethod
    def _extract_values_from_models(values: Iterable[Any]) -> Iterator[str]:
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
            self.__dict__["values"] = values
        return self

    @validate_call
    def check(self, item: PathInputType, *_, **__) -> bool:
        return self.path_mapper.unmap(item, check_existence=False) in self.values
