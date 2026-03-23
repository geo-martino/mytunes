import logging
import re
from collections.abc import Collection
from functools import cached_property

from tabulate import tabulate

from musify.logger import Logger
from musify.models._base import BaseModel


def generate_table(rows: Collection[Collection[str]]) -> str:
    """Generate a table for logging from the given rows."""
    col_count = max(map(len, rows)) if rows else 0
    table = tabulate(
        rows,
        tablefmt="orgtbl",
        colalign=("left", *["right"] * max(0, col_count - 1)),
    )
    table = re.sub(r"\| +\|", "|", table)
    table = re.sub(r"\| +\|", "|", table)
    return table


class HasLogger(BaseModel):
    """Represents a resource that has a logger."""

    @cached_property
    def logger(self) -> Logger:
        # noinspection PyTypeChecker
        return logging.getLogger(__name__)
