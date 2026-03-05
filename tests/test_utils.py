from copy import deepcopy
from typing import Annotated

import pytest
from pydantic import StringConstraints

from musify.exception import MusifyTypeError
from musify.utils import flatten_nested, merge_maps, get_most_common_values, unicode_len, get_base_types
from musify.utils import limit_value, to_collection
from musify.utils import strip_ignore_words, safe_format_map, get_max_width, align_string


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


def test_safe_format_map():
    test = {
        "a": "please {replace_me}",
        "b": {"nested1": "{replace_me}", "nested2": "no {replacement}"},
        "c": {"nested1": {"nested2a": "{replace_me} too", "nested2b": "don't replace_me"}},
        "d": "{don't fail}"
    }
    replacements = {"replace_me": "new value"}
    safe_format_map(test, format_map=replacements)

    assert test == {
        "a": "please new value",
        "b": {"nested1": "new value", "nested2": "no {replacement}"},
        "c": {"nested1": {"nested2a": "new value too", "nested2b": "don't replace_me"}},
        "d": "{don't fail}"
    }


def test_get_max_width():
    values = ["a" * 10, "b" * 15, "c" * 20, "d" * 25, "e" * 30]

    assert get_max_width(values, min_width=5, max_width=8) == 8
    assert get_max_width(values, min_width=5, max_width=22) == 22
    assert get_max_width(values, min_width=5, max_width=50) == 31  # +1 for trailing space
    assert get_max_width(values, min_width=50, max_width=100) == 50

    assert get_max_width([], min_width=10) == 10


def test_align_string_truncate_left():
    assert align_string("123456789", max_width=0, truncate_left=False) == ""
    assert align_string("123456789", max_width=1, truncate_left=False) == "1"
    assert align_string("123456789", max_width=2, truncate_left=False) == "12"
    assert align_string("123456789", max_width=3, truncate_left=False) == "123"
    assert align_string("123456789", max_width=4, truncate_left=False) == "123."
    assert align_string("123456789", max_width=5, truncate_left=False) == "123.."
    assert align_string("123456789", max_width=6, truncate_left=False) == "123..."
    assert align_string("123456789", max_width=7, truncate_left=False) == "1234..."
    assert align_string("123456789", max_width=8, truncate_left=False) == "12345..."
    assert align_string("123456789", max_width=9, truncate_left=False) == "123456789"
    assert align_string("123456789", max_width=10, truncate_left=False) == "123456789" + " "
    assert align_string("123456789", max_width=14, truncate_left=False) == "123456789" + " " * 5


def test_align_string_truncate_right():
    assert align_string("123456789", max_width=0, truncate_left=True) == ""
    assert align_string("123456789", max_width=1, truncate_left=True) == "9"
    assert align_string("123456789", max_width=2, truncate_left=True) == "89"
    assert align_string("123456789", max_width=3, truncate_left=True) == "789"
    assert align_string("123456789", max_width=4, truncate_left=True) == ".789"
    assert align_string("123456789", max_width=5, truncate_left=True) == "..789"
    assert align_string("123456789", max_width=6, truncate_left=True) == "...789"
    assert align_string("123456789", max_width=7, truncate_left=True) == "...6789"
    assert align_string("123456789", max_width=8, truncate_left=True) == "...56789"
    assert align_string("123456789", max_width=9, truncate_left=True) == "123456789"
    assert align_string("123456789", max_width=10, truncate_left=True) == "123456789" + " "
    assert align_string("123456789", max_width=14, truncate_left=True) == "123456789" + " " * 5


def test_align_string_short():
    assert align_string("", max_width=1, truncate_left=False) == " "
    assert align_string("", max_width=3, truncate_left=False) == " " * 3
    assert align_string("", max_width=5, truncate_left=False) == " " * 5
    assert align_string("a", max_width=3, truncate_left=False) == "a  "
    assert align_string("abcd", max_width=4, truncate_left=False) == "abcd"


def test_align_string_unicode_truncate_left():
    value_emoji_1 = "🏗️🐧🎙️👢🥾"
    assert align_string(value_emoji_1, max_width=1) == "."
    assert align_string(value_emoji_1, max_width=2) == "🏗️"
    assert align_string(value_emoji_1, max_width=3) == "🏗️."
    assert align_string(value_emoji_1, max_width=4) == "🏗️.."
    assert align_string(value_emoji_1, max_width=5) == "🏗️..."
    assert align_string(value_emoji_1, max_width=6) == "🏗️... "
    assert align_string(value_emoji_1, max_width=7) == "🏗️🐧..."
    assert align_string(value_emoji_1, max_width=8) == "🏗️🐧... "
    assert align_string(value_emoji_1, max_width=9) == "🏗️🐧🎙️..."
    assert align_string(value_emoji_1, max_width=10) == "🏗️🐧🎙️👢🥾"
    assert align_string(value_emoji_1, max_width=11) == "🏗️🐧🎙️👢🥾" + " "
    assert align_string(value_emoji_1, max_width=15) == "🏗️🐧🎙️👢🥾" + " " * 5

    value_emoji_2 = "text 🏗️🐧🎙️👢🥾🎙️"  # actual length == 14
    assert len(value_emoji_2) != unicode_len(value_emoji_2)  # fixed-width length == 17
    assert len(align_string(value_emoji_2, max_width=24)) == 21  # diff = actual length - fixed-width length
    assert unicode_len(align_string(value_emoji_2, max_width=24)) == 24
    assert align_string(value_emoji_2, max_width=17) == "text 🏗️🐧🎙️👢🥾🎙️"
    assert align_string(value_emoji_2, max_width=16) == "text 🏗️🐧🎙️👢..."
    assert align_string(value_emoji_2, max_width=15) == "text 🏗️🐧🎙️... "
    assert align_string(value_emoji_2, max_width=14) == "text 🏗️🐧🎙️..."
    assert align_string(value_emoji_2, max_width=13) == "text 🏗️🐧... "


def test_align_string_unicode_truncate_right():
    value_emoji_1 = "🥾👢🎙️🐧🏗️"
    assert align_string(value_emoji_1, max_width=1, truncate_left=True) == "."
    assert align_string(value_emoji_1, max_width=2, truncate_left=True) == "🏗️"
    assert align_string(value_emoji_1, max_width=3, truncate_left=True) == ".🏗️"
    assert align_string(value_emoji_1, max_width=4, truncate_left=True) == "..🏗️"
    assert align_string(value_emoji_1, max_width=5, truncate_left=True) == "...🏗️"
    assert align_string(value_emoji_1, max_width=6, truncate_left=True) == "...🏗️ "
    assert align_string(value_emoji_1, max_width=7, truncate_left=True) == "...🐧🏗️"
    assert align_string(value_emoji_1, max_width=8, truncate_left=True) == "...🐧🏗️ "
    assert align_string(value_emoji_1, max_width=9, truncate_left=True) == "...🎙️🐧🏗️"
    assert align_string(value_emoji_1, max_width=10, truncate_left=True) == "🥾👢🎙️🐧🏗️"
    assert align_string(value_emoji_1, max_width=11, truncate_left=True) == "🥾👢🎙️🐧🏗️" + " "
    assert align_string(value_emoji_1, max_width=15, truncate_left=True) == "🥾👢🎙️🐧🏗️" + " " * 5

    value_emoji_2 = "text 🎙️🥾👢🎙️🐧🏗️"  # actual length == 14
    assert len(value_emoji_2) != unicode_len(value_emoji_2)  # fixed-width length == 17
    assert len(align_string(value_emoji_2, max_width=24, truncate_left=True)) == 21
    assert unicode_len(align_string(value_emoji_2, max_width=24, truncate_left=True)) == 24
    assert align_string(value_emoji_2, max_width=17, truncate_left=True) == "text 🎙️🥾👢🎙️🐧🏗️"
    assert align_string(value_emoji_2, max_width=16, truncate_left=True) == "... 🎙️🥾👢🎙️🐧🏗️"
    assert align_string(value_emoji_2, max_width=15, truncate_left=True) == "...🎙️🥾👢🎙️🐧🏗️"
    assert align_string(value_emoji_2, max_width=14, truncate_left=True) == "...🥾👢🎙️🐧🏗️ "
    assert align_string(value_emoji_2, max_width=13, truncate_left=True) == "...🥾👢🎙️🐧🏗️"


###########################################################################
## Number
###########################################################################
def test_limit_value():
    assert limit_value(6, 0, 20) == 6
    assert limit_value(-5, 10, 20) == 10
    assert limit_value(-5, -20, 20) == -5
    assert limit_value(-5, -2, 20) == -2
    assert limit_value(30, -2, 20) == 20

    assert limit_value(0.12, 0.5, 1) == 0.5
    assert limit_value(2, 0.5, 1.8) == 1.8
    assert limit_value(1, 0.5, 1.8) == 1


###########################################################################
## Collection
###########################################################################
# noinspection PyTypeChecker
def test_to_collection():
    # None input always returns None
    assert to_collection(None) is None
    assert to_collection(None, list) is None
    assert to_collection(None, set) is None
    assert to_collection(None, tuple) is None
    assert to_collection(None, dict) is None
    assert to_collection(None, str) is None

    # input always equals output on equal types
    assert to_collection("123", str) == "123"
    assert to_collection(123, int) == 123
    assert to_collection({1: "a", 2: "b", 3: "c"}, dict) == {1: "a", 2: "b", 3: "c"}

    # converts to tuple (default)
    assert to_collection("123") == ("123",)
    assert to_collection(1) == (1,)
    assert to_collection([1, 2, 3]) == (1, 2, 3)
    assert to_collection({1, 2, 3, 4}) == (1, 2, 3, 4)
    assert to_collection({1: "a", 2: "b", 3: "c"}) == ({1: "a", 2: "b", 3: "c"},)

    # converts to set
    assert to_collection("123", set) == {"123"}
    assert to_collection(1, set) == {1}
    assert to_collection([1, 2, 3], set) == {1, 2, 3}
    assert to_collection({1, 2, 3, 4}, set) == {1, 2, 3, 4}

    # converts to list
    assert to_collection("123", list) == ["123"]
    assert to_collection(1, list) == [1]
    assert to_collection([1, 2, 3], list) == [1, 2, 3]
    assert to_collection({1, 2, 3, 4}, list) == [1, 2, 3, 4]
    assert to_collection({1: "a", 2: "b", 3: "c"}, list) == [{1: "a", 2: "b", 3: "c"}]

    # fails on unrecognised type
    with pytest.raises(MusifyTypeError):
        to_collection("123", dict)
        to_collection(1, str)
        to_collection([1, 2, 3], bool)
        to_collection({1, 2, 3, 4}, float)


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


def tests_merge_maps():
    source = {
        1: "value",
        2: {"a": "val a", "b": "val b", "c": {"nested1": "nested val"}},
        3: {"nested1": {"nested2": {"nested3": "old value"}}},
        4: {"a": [1, 2, 3]}
    }
    new = {
        2: {"b": "new value b", "c": {"nested1": "modified nested val"}},
        3: {"nested1": {"nested2": {"nested3": "new value", "new key": "new val"}}},
        4: {"a": [4, 5]}
    }

    test = deepcopy(source)
    merge_maps(source=test, new=new, extend=False, overwrite=False)
    assert test == {
        1: "value",
        2: {"a": "val a", "b": "val b", "c": {"nested1": "nested val"}},
        3: {"nested1": {"nested2": {"nested3": "old value", "new key": "new val"}}},
        4: {"a": [1, 2, 3]}
    }

    test = deepcopy(source)
    merge_maps(source=test, new=new, extend=False, overwrite=True)
    assert test == {
        1: "value",
        2: {"a": "val a", "b": "new value b", "c": {"nested1": "modified nested val"}},
        3: {"nested1": {"nested2": {"nested3": "new value", "new key": "new val"}}},
        4: {"a": [4, 5]}
    }

    test = deepcopy(source)
    merge_maps(source=test, new=new, extend=True, overwrite=False)
    assert test == {
        1: "value",
        2: {"a": "val a", "b": "val b", "c": {"nested1": "nested val"}},
        3: {"nested1": {"nested2": {"nested3": "old value", "new key": "new val"}}},
        4: {"a": [1, 2, 3, 4, 5]}
    }


###########################################################################
## Misc
###########################################################################
def test_get_most_common_values():
    assert get_most_common_values([1, 1, 2, 3, 3, 3, 4]) == [3, 1, 2, 4]
    assert get_most_common_values(["asd", 6, "five", "asd", "five", "asd"]) == ["asd", "five", 6]


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
