from copy import deepcopy
from typing import Annotated

import pytest
from pydantic import StringConstraints

from musify.exception import MusifyTypeError
from musify.utils import flatten_nested, strip_ignore_words, get_base_types


###########################################################################
## String
###########################################################################
def test_strip_ignore_words():
    # marks as not special
    assert strip_ignore_words("Hello", None) == (True, True, "Hello")
    assert strip_ignore_words("I am a string", ["A"]) == (True, True, "I am a string")
    assert strip_ignore_words("special end??", ["A"]) == (True, True, "special end??")

    # marks as special
    assert strip_ignore_words("!special1", ["special"]) == (False, True, "special1")
    assert strip_ignore_words("*%2I am very special!", ["very", "i"]) == (False, True, "2I am very special!")

    # marks as special as needed and strips words
    assert strip_ignore_words("I am a string", ["i"]) == (True, False, "am a string")
    assert strip_ignore_words("*%I   am very special!", ["am", "i"]) == (False, False, "am very special!")


###########################################################################
## Mapping
###########################################################################
def test_flatten_nested():
    # flattens non-nested
    assert flatten_nested({"a": 1, "b": 2, "c": 3}) == [1, 2, 3]
    assert flatten_nested({"a": 1, "b": [2, 3, 4], "c": 5}) == [1, 2, 3, 4, 5]

    # flattens nested
    nested_map = {"a": 1, "b": [2, 3, 4], "c": {"sub1": 5, "sub2": [6], "sub3": {"deep": [7, 8]}}}
    assert flatten_nested(nested_map) == [1, 2, 3, 4, 5, 6, 7, 8]
    assert flatten_nested(nested_map, ["a", "b"]) == ["a", "b", 1, 2, 3, 4, 5, 6, 7, 8]


###########################################################################
## Misc
###########################################################################
def test_get_base_types_basic():
    assert get_base_types(str) == (str,)
    assert get_base_types(int) == (int,)
    assert get_base_types(dict[str, int]) == (dict,)


def test_get_base_types_union():
    # noinspection PyTypeHints
    type annotation = str | int | float | bool | None
    expected = (str, int, float, bool, type(None))

    assert get_base_types(annotation) == expected
    assert get_base_types(str | int | float | bool | None) == expected


def test_get_base_types_generic():
    assert get_base_types(dict[str, int] | int | tuple[int, ...]) == (dict, int, tuple)


def test_get_base_types_annotated():
    assert get_base_types(Annotated[str, StringConstraints(min_length=1)]) == (str,)
