import builtins
from collections.abc import Generator
from contextlib import contextmanager
from unittest import mock
from unittest.mock import patch


@contextmanager
def patch_input(values: list[str]) -> Generator[mock.Mock, None, None]:
    """``builtins.input`` calls will return the ``values`` in order, finishing on ''"""
    def input_return(*_, **__) -> str:
        """An order of return values for user input that will test various stages of the pause"""
        return values.pop(0) if values else ""

    with patch.object(builtins, "input", new=input_return) as mock_input:
        yield mock_input
