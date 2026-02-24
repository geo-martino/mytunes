import logging
from functools import cached_property

from musify.logger import MusifyLogger
from musify.models._base import MusifyModel


class HasLogger(MusifyModel):
    """Represents a resource that has a logger."""

    @cached_property
    def logger(self) -> MusifyLogger:
        # noinspection PyTypeChecker
        return logging.getLogger(__name__)
