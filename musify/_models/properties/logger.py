import logging
from contextlib import AbstractAsyncContextManager
from functools import cached_property
from typing import Self

from musify.logger import Logger
from .._base import BaseModel


class HasLogger(BaseModel, AbstractAsyncContextManager):
    """Represents a resource that has a logger."""

    @cached_property
    def logger(self) -> Logger:
        return logging.getLogger(__name__)

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        self.logger.__enter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.logger.__exit__(exc_type, exc_val, exc_tb)
        return await super().__aexit__(exc_type, exc_val, exc_tb)
