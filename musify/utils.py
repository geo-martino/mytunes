"""
Generic utility functions and classes which can be used throughout the entire package.
"""
import re
from collections.abc import Iterable, MutableSequence, MutableMapping
from types import UnionType, GenericAlias
from typing import Any, TypeVar, get_args, TypeAliasType, ForwardRef, Union

from typing_extensions import get_origin, evaluate_forward_ref
from typing_inspection.typing_objects import is_annotated

###########################################################################
## String
###########################################################################
IGNORE_WORDS_DEFAULT = frozenset({"The", "A"})


def strip_ignore_words(value: str, words: Iterable[str] | None = IGNORE_WORDS_DEFAULT) -> tuple[bool, bool, str]:
    """
    Remove ignorable words from the beginning of a string.

    Useful for sorting collections strings with ignorable start words and/or special characters.
    Only removes the first word it finds at the start of the string.

    :return: Tuple of (True if the string starts with some special character, the formatted string)
    """
    if not value:
        return False, True, value

    special_chars = list('!"£$%^&*()_+-=…')
    special_start = any(value.startswith(c) for c in special_chars)
    value = re.sub(r"^\W+", "", value).strip()

    if not words:
        return not special_start, True, value

    new_value = value
    trimmed = False
    for word in words:
        new_value = re.sub(rf"^{word}\s+", "", value, flags=re.I)
        if new_value != value:
            trimmed = True
            break

    return not special_start, not trimmed, new_value


###########################################################################
## Mapping
###########################################################################
def flatten_nested[T: Any](nested: MutableMapping, previous: MutableSequence[T] | None = None) -> list[T]:
    """Flatten the final layers of the values of a nested map to a single list"""
    if previous is None:
        previous = []

    if isinstance(nested, MutableMapping):
        for key, value in nested.items():
            flatten_nested(value, previous=previous)
    elif isinstance(nested, (list, set, tuple)):
        previous.extend(nested)
    else:
        previous.append(nested)

    return previous


###########################################################################
## Misc
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
