from annotationlib import ForwardRef
from collections.abc import Iterable, Mapping
from types import UnionType, GenericAlias
from typing import Annotated, Any, TypeAliasType, get_args, evaluate_forward_ref, Union, TypeVar
from typing_extensions import get_origin

from annotated_types import MinLen
from pydantic import StringConstraints, BeforeValidator
from pydantic.alias_generators import to_snake
from typing_inspection.typing_objects import is_annotated


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
    from musify.models import BaseModel  # to prevent cyclical imports

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
    from musify.models import BaseModel  # to prevent cyclical imports

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
    from musify.models import BaseModel  # to prevent cyclical imports

    match value:
        case None:
            return
        case str() | Mapping() | BaseModel():
            return [value]
        case Iterable():
            return list(value)
        case _:
            return [value]


###########################################################################
## Utilities
###########################################################################
def get_base_types(
        annotation: type | UnionType | GenericAlias | TypeAliasType,
        ignore_none: bool = True,
        resolve_generics: bool = False,
) -> tuple[type, ...]:
    """
    Get all base types for a given type annotation.

    :param annotation: The type annotation to get the base types for.
    :param ignore_none: Whether to drop NoneType base types.
    :param resolve_generics: Whether to resolve TypeVars to their constraints or bounds.
    :return: A tuple of all base types.
    """
    bases = []
    match annotation:
        case UnionType():
            for kls in get_args(annotation):
                bases.extend(get_base_types(kls, ignore_none=ignore_none, resolve_generics=resolve_generics))
        case GenericAlias():
            bases.append(get_origin(annotation))
        case ForwardRef():
            annotation = evaluate_forward_ref(annotation)
            bases.extend(get_base_types(annotation, ignore_none=ignore_none, resolve_generics=resolve_generics))
        case TypeAliasType():
            ano = annotation.__value__
            bases.extend(get_base_types(ano, ignore_none=ignore_none, resolve_generics=resolve_generics))
        case _ if is_annotated(get_origin(annotation)):
            ano = annotation.__origin__
            bases.extend(get_base_types(ano, ignore_none=ignore_none, resolve_generics=resolve_generics))
        case _:
            bases.append(annotation)

    if ignore_none:
        bases = [b for b in bases if b is not type(None)]
        for i, b in enumerate(bases):
            if type(None) in (args := get_args(b)):
                bases[i] = Union[*(arg for arg in args if arg is not type(None))]

    if resolve_generics:
        for i, b in enumerate(bases):
            if not isinstance(b, TypeVar):
                continue

            if b.__constraints__:
                bases[i] = Union[*b.__constraints__]
            elif b.__bound__ is not None:
                bases[i] = b.__bound__

    return tuple(bases)
