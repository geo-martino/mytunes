import builtins
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from unittest.mock import patch, Mock


@contextmanager
def patch_input(values: Iterator[str]) -> Generator[Mock, None, None]:
    """``builtins.input`` calls will return the ``values`` in order, finishing on ''"""
    def input_return(*_, **__) -> str:
        """An order of return values for user input that will test various stages of the pause"""
        return str(next(values, ""))

    with patch.object(builtins, "input", side_effect=input_return) as mock_input:
        yield mock_input
