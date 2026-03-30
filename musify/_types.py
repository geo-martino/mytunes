from collections.abc import Iterable, Mapping
from typing import Annotated, Any

from annotated_types import MinLen
from pydantic import StringConstraints, BeforeValidator
from pydantic.alias_generators import to_snake

from musify.models import BaseModel

type Character = Annotated[str, StringConstraints(min_length=1, max_length=1)]
type StrippedCharacter = Annotated[str, StringConstraints(min_length=1, max_length=1, strip_whitespace=True)]
type String = Annotated[str, StringConstraints(min_length=1)]
type StrippedString = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]
type LowerStrippedString = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True, to_lower=True)]
type UpperStrippedString = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True, to_upper=True)]
type LowerSnakeCase = Annotated[
    str,
    StringConstraints(min_length=1, strip_whitespace=True, to_lower=True),
    BeforeValidator(to_snake),
]
type UpperSnakeCase = Annotated[
    str,
    StringConstraints(min_length=1, strip_whitespace=True, to_upper=True),
    BeforeValidator(to_snake),
]
type ListWithValues[T] = Annotated[list[T], MinLen(1)]

type Number = int | float


def to_set(value: Any) -> set[Any] | None:
    """Converts a value to a set."""
    match value:
        case None:
            return
        case str() | Mapping() | BaseModel():
            return {value}
        case Iterable():
            return set(value)
        case _:
            return {value}


def to_tuple(value: Any) -> tuple[Any] | None:
    """Converts a value to a tuple."""
    match value:
        case None:
            return
        case str() | Mapping() | BaseModel():
            return (value,)
        case Iterable():
            return tuple(value)
        case _:
            return (value,)


def to_list(value: Any) -> list[Any] | None:
    """Converts a value to a list."""
    match value:
        case None:
            return
        case str() | Mapping() | BaseModel():
            return [value]
        case Iterable():
            return list(value)
        case _:
            return [value]
