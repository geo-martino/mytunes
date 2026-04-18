"""Utilities to use in tests. Usually used for setting up testing conditions."""
import builtins
import itertools
import math
from collections.abc import Collection, Iterator, Generator
from contextlib import contextmanager
from random import choice
from unittest.mock import Mock, patch


def split_list[T](lst: Collection[T], n: int = None, overlap: int = 0) -> Iterator[list[T]]:
    """
    Split a list into n sub-lists of approximately equal size.

    :param lst: The list to split.
    :param n: The number of sub-lists to create.
    :param overlap: The number of overlapping elements between sub-lists.
    """
    if n is None:
        n = choice(range(1, len(lst) + 1))
    if overlap >= len(lst):
        raise ValueError("Overlap must be less than the size of the list.")

    def _get_batcher():
        # noinspection PyTypeChecker
        return map(list, itertools.batched(lst, size))

    size = math.ceil((len(lst) + 1) / n)
    batcher_left = _get_batcher()
    batcher_right = _get_batcher()
    next(batcher_right)

    overlap_result = []
    for item in batcher_left:
        overlap_batch = next(batcher_right, [])[:overlap]
        overlap_result.extend(overlap_batch)
        yield item + overlap_batch

    if overlap:
        yield overlap_result


@contextmanager
def patch_input(values: Iterator[str]) -> Generator[Mock]:
    """``builtins.input`` calls will return the ``values`` in order, finishing on ''"""
    def input_return(*_, **__) -> str:
        """An order of return values for user input that will test various stages of the pause"""
        return str(next(values, ""))

    with patch.object(builtins, "input", side_effect=input_return) as mock_input:
        yield mock_input
