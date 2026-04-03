import logging
from functools import cached_property
from typing import Self, AsyncContextManager

from musify.logger import Logger
from musify.models._base import BaseModel


class HasLogger(BaseModel, AsyncContextManager):
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
