"""
Generic utility functions and classes which can be used throughout the entire package.
"""
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Collection, MutableSequence, Mapping, MutableMapping
from typing import Any, TypeVar, get_args, TypeAliasType

from aiorequestful.types import Number

from musify.exception import MusifyTypeError, MusifyImportError


###########################################################################
## Properties
###########################################################################
# noinspection PyPep8Naming
class classproperty:
    """Set an immutable class property with this decorator"""
    def __init__(self, func):
        self.fget = func

    def __get__(self, instance, owner):
        return self.fget(owner)


###########################################################################
## Extended primitives
###########################################################################
class SafeDict(dict):
    """Extends dict to ignore missing keys when using format_map operations"""

    __slots__ = ()

    def __missing__(self, key):
        return "{" + key + "}"


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


def safe_format_map[T](value: T, format_map: Mapping[str, Any]) -> T:
    """
    Apply a ``format_map`` to a given ``value`` ignoring missing keys.
    If ``value`` is a map, apply the ``format_map`` recursively.
    """
    if not isinstance(format_map, SafeDict):
        format_map = SafeDict(**format_map)

    if isinstance(value, MutableMapping):
        for k, v in value.items():
            value[k] = safe_format_map(v, format_map)
    elif isinstance(value, str) and '{' in value and '}' in value:
        value = value.format_map(format_map)
    return value


_UNICODE_MODIFIERS = {"Mc", "Mn"}
_UNICODE_DOUBLE_WIDTH = {"So"}


def unicode_len(value: str) -> int:
    """
    Returns the visible length of ``value`` when rendered with fixed-width font.

    Takes into account unicode characters which render with varying widths.
    """
    length = sum(unicodedata.category(char) not in _UNICODE_MODIFIERS for char in value)
    length += sum(unicodedata.category(char) in _UNICODE_DOUBLE_WIDTH for char in value)  # takes up 2 spaces
    return length


def unicode_reversed(value: str) -> str:
    """Returns a reversed string or ``value`` keeping unicode characters which combine in the correct order"""
    value_reversed = ""
    char_combined = ""

    for i, char in enumerate(value):
        char_combined += char
        if i + 1 < len(value) and unicodedata.category(value[i + 1]) in _UNICODE_MODIFIERS:
            continue

        value_reversed = char_combined + value_reversed
        char_combined = ""
    return value_reversed


def get_max_width(values: Collection[Any], min_width: int = 15, max_width: int = 50) -> int:
    """
    Get max width of given list of ``values`` for column-aligned logging.

    Uses width as would be seen in a fixed-width font taking into account characters with varying widths.
    """
    if len(values) == 0:
        return min_width
    max_len = unicode_len(max(map(str, values), key=unicode_len))
    return limit_value(value=max_len + 1, floor=min_width, ceil=max_width)


def align_string(value: Any, max_width: int = 0, truncate_left: bool = False) -> str:
    """
    Align string with space padding and truncate any string longer than ``max_width`` with ``...``

    This function aligns based on fixed-width fonts.
    Therefore, unicode characters (e.g. emojis) will be aligned based on their width in a fixed-width font.

    :param value: The value to be aligned. Will first be converted to a string.
    :param max_width: The expected width (i.e. number of fixed-width characters)
        the string should occupy in a fixed-width font.
    :param truncate_left: When truncating, truncate the left (i.e. start) of the string.
    :return: The padded and truncated string with visible length == ``max_width``.
    """
    value_str = str(value)
    if not value_str or max_width == 0:
        return " " * max_width

    if truncate_left:  # reverse string for truncate right operations
        value_str = unicode_reversed(value_str)

    value_truncated = ""
    dots_count = limit_value(max_width - 3, 0, 3) if max_width < unicode_len(value_str) else 0
    expected_len = max_width - dots_count
    for char in value_str:
        # stop on double width characters and extend dots_count to cover missing character if needed
        if unicodedata.category(char) in _UNICODE_DOUBLE_WIDTH and unicode_len(value_truncated + char) > expected_len:
            dots_count += 1 if dots_count < 3 and unicode_len(value_truncated) < max_width else 0
            break

        # always add unicode modifiers even if unicode_len == expected_width
        if unicodedata.category(char) not in _UNICODE_MODIFIERS and unicode_len(value_truncated) == expected_len:
            break

        value_truncated += char

    value_truncated += "." * dots_count  # add ellipses

    if truncate_left:  # reverse back
        value_truncated = unicode_reversed(value_truncated)

    # extend max_width with difference in length from actual len to unicode_len
    max_width += len(value_truncated) - unicode_len(value_truncated)
    return f"{value_truncated:<{max_width}.{max_width}}"


###########################################################################
## Number
###########################################################################
def limit_value(value: Number, floor: Number = 1, ceil: Number = 50) -> Number:
    """Limit a given ``value`` to always be between some ``floor`` and ``ceil``"""
    return max(min(value, ceil), floor)


###########################################################################
## Collection
###########################################################################
UT = TypeVar("UT")
CollT = UT | list[UT] | tuple[UT] | set[UT]


def to_collection[T: Any](data: T | CollT, cls: type[CollT] = tuple) -> T | CollT | None:
    """
    Safely turn any object into a collection of a given type ``T``.

    Strings are converted to collections of size 1 where the first element is the string.
    Returns None if value is None.
    """
    if data is None or isinstance(data, cls):
        return data
    elif isinstance(data, Iterable) and not isinstance(data, str) and not isinstance(data, Mapping):
        return cls(data)
    elif cls is tuple:
        return (data,)
    elif cls is set:
        return {data}
    elif cls is list:
        return [data]
    raise MusifyTypeError(f"Unable to convert data to {cls.__name__} (data={data})")


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


def merge_maps[T: MutableMapping](source: T, new: Mapping, extend: bool = True, overwrite: bool = False) -> T:
    """
    Recursively update a given ``source`` map in place with a ``new`` map.

    :param source: The source map.
    :param new: The new map with values to update for the source map.
    :param extend: When a value is a list and a list is already present in the source map, extend the list when True.
        When False, only replace the list if overwrite is True.
    :param overwrite: When True, overwrite any value in the source destructively.
    :return: The updated dict.
    """
    def is_collection(value: Any) -> bool:
        """Return True if ``value`` is of type ``Collection`` and not a string or map"""
        return isinstance(value, Collection) and not isinstance(value, str) and not isinstance(value, Mapping)

    for k, v in new.items():
        if isinstance(v, Mapping) and isinstance(source.get(k, {}), Mapping):
            source[k] = merge_maps(source.get(k, {}), v, extend=extend, overwrite=overwrite)
        elif extend and is_collection(v) and is_collection(source.get(k, [])):
            source[k] = to_collection(source.get(k, []), list) + to_collection(v, list)
        elif overwrite or source.get(k) is None:
            source[k] = v
    return source


###########################################################################
## Misc
###########################################################################
def get_most_common_values(values: Iterable[Any]) -> list[Any]:
    """Get an ordered list of the most common values for a given collection of ``values``"""
    return [x[0] for x in Counter(values).most_common()]


def get_user_input(text: str | None = None) -> str:
    """Print formatted dialog with optional text and get the user's input."""
    return input(f"\33[93m{text}\33[0m | ").strip()


def required_modules_installed(modules: list, this: object = None) -> bool:
    """Check the required modules are installed, raise :py:class:`MusifyImportError` if not."""
    modules_installed = all(module is not None for module in modules)
    if not modules_installed and this is not None:
        names = [name for name, obj in globals().items() if obj in modules and not name.startswith("_")]
        if isinstance(this, str):
            message = f"Cannot run {this}. Required modules: {", ".join(names)}"
        else:
            message = f"Cannot create {this.__name__} object. Required modules: {", ".join(names)}"

        raise MusifyImportError(message)

    return modules_installed


def get_discriminator_values(cls: TypeAliasType, key: str = "format") -> set[str]:
    """
    Get all possible discriminator values for a given ``cls`` which is a :py:class:`TypeAliasType`.

    :param cls: The type alias to get the discriminator values for.
    :param key: The key of the discriminator field.
    :return: A set of all possible discriminator values.
    """
    if not isinstance(cls, TypeAliasType):
        raise MusifyTypeError(f"Cannot get discriminator values for non-TypeAliasType: {cls}")

    return {
        arg
        for t in get_args(get_args(cls.__value__)[0])
        for arg in get_args((t.model_fields[key]).annotation)
    }