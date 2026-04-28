from pathlib import Path
from collections.abc import Iterable, Iterator, Mapping, Hashable, Collection, Sequence
from typing import Annotated, Any, Self, final, Literal

from pydantic import BeforeValidator, Field, model_validator, validate_call, field_validator

from mytunes._types import StrippedString, TO_SET, TO_TUPLE, DEFAULT_IF_NONE
from ..._base import BaseModel
from mytunes.core.properties.file import IsLocalFile
from mytunes.core.properties.path import PathInputType, PathModelMapper
from mytunes.core.properties.path import PathMapper
from mytunes.core.properties.name import HasName
from mytunes.processors.filters._base import Filter


class _ValueFilter[FT: str, IT: Any](Filter[FT, IT]):
    """Filter based on a defined list of values."""
    values: Annotated[Sequence[IT], TO_TUPLE] = Field(
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

    def check(self, item: Any, reference: Any | None = None) -> bool:
        return item in self.values

    def __iter__(self):
        return iter(self.values)

    def __len__(self):
        return len(self.values)

    def __contains__(self, item: Any):
        return item in self.values


@final
class ValueFilter[IT: Any](_ValueFilter[Literal["value", "values"], IT]):
    __final__ = True


@final
class NameFilter(_ValueFilter[Literal["name", "names"], str]):
    """Filter based on a defined list of name values."""
    __final__ = True

    values: Annotated[set[StrippedString], TO_SET] = Field(
        description="Set of names to filter against.",
        default_factory=set,
    )

    @field_validator("values", mode="before", check_fields=True)
    @classmethod
    def _extract_values_from_models(cls, values: Iterable[Any]) -> set[str]:
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

    @classmethod
    def from_names[T](cls, data: T | str | Collection[str]) -> T | NameFilter:
        if isinstance(data, str):
            data = (data,)
        if not isinstance(data, Collection) or not all(isinstance(it, str) for it in data):
            return data
        return NameFilter(values=data)

    @validate_call
    def check[T: str | HasName](self, item: T, reference: T | None = None) -> bool:
        name = self._extract_value_from_model(item)
        return isinstance(name, Hashable) and super().check(name, reference=reference)


@final
class PathFilter(_ValueFilter[Literal["path", "paths"], str]):
    """Filter based on a defined list of path values."""
    __final__ = True

    values: Annotated[set[StrippedString], TO_SET] = Field(
        description="Set of paths to filter against. These will be stored as un-mapped paths if a PathMapper is set.",
        default_factory=set,
    )
    path_mapper: Annotated[PathMapper.annotation, DEFAULT_IF_NONE] = Field(
        description="Mapper to use to map paths.",
        default_factory=PathModelMapper,
    )

    @property
    def paths(self) -> set[Path]:
        """Get the values as Path objects."""
        paths = self.values
        if self.path_mapper is not None:
            paths = self.path_mapper.serialise_many(paths, check_existence=False)
        return set(map(Path, paths))

    @paths.setter
    def paths(self, value: set[Path]) -> None:
        self.values = set(map(str, value))

    @property
    def paths_valid(self) -> set[Path]:
        """Get the values as Path objects, only returning those that exist."""
        paths = self.values
        if self.path_mapper is not None:
            paths = filter(None, self.path_mapper.serialise_many(paths, check_existence=True))
        return set(map(Path, paths))

    @field_validator("values", mode="before", check_fields=True)
    @classmethod
    def _extract_values_from_models(cls, values: Iterable[Any]) -> set[str]:
        return set(map(cls._extract_value_from_model, values))

    @staticmethod
    def _extract_value_from_model(item: Any) -> str:
        match item:
            case str():
                return item
            case Path():
                return str(item)
            case IsLocalFile():
                return str(item.path)
            case _:
                return item

    @model_validator(mode="after")
    def _unmap_paths(self) -> Self:
        if self.path_mapper is None:
            return self

        values = set(self.path_mapper.deserialise_many(self.values, check_existence=False))
        if values != self.values:
            self.__dict__["values"] = values
        return self

    @validate_call
    def check(self, item: PathInputType, reference: PathInputType | None = None) -> bool:
        path = self._extract_value_from_model(item)
        path = self.path_mapper.deserialise(path, check_existence=False)
        return isinstance(path, Hashable) and super().check(path, reference=reference)
