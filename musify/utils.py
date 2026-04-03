from collections.abc import Callable, AsyncGenerator
from typing import AsyncIterable

from pydantic_core import PydanticUseDefault


def default_if_none[T](value: T) -> T:
    """Use the Pydantic default if value is None."""
    if value is None:
        raise PydanticUseDefault()
    return value


async def afilter[T](predicate: Callable[[T], bool] | None, iterable: AsyncIterable[T]) -> AsyncGenerator[T]:
    async for item in iterable:
        if predicate is None:
            if item:
                yield item
        elif predicate(item):
            yield item
