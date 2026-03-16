import functools
import logging
from functools import cached_property
from inspect import iscoroutine, isawaitable

from musify.logger import Logger
from musify.models._base import BaseModel


class HasLogger(BaseModel):
    """Represents a resource that has a logger."""

    @cached_property
    def logger(self) -> Logger:
        # noinspection PyTypeChecker
        return logging.getLogger(__name__)
