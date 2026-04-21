from typing import Annotated

from mytunes._types import get_base_types
from pydantic import StringConstraints


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
    expected = (str, int, float, bool)

    assert get_base_types(annotation, ignore_none=False) == tuple(list(expected) + [type(None)])
    assert get_base_types(str | int | float | bool | None, ignore_none=True) == expected


def test_get_base_types_generic():
    assert get_base_types(dict[str, int] | int | tuple[int, ...]) == (dict, int, tuple)


def test_get_base_types_annotated():
    assert get_base_types(Annotated[str, StringConstraints(min_length=1)]) == (str,)
