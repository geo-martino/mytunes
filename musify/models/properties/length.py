from __future__ import annotations

import re
from datetime import timedelta
from functools import reduce, total_ordering
from operator import mul
from typing import Any

from pydantic import PositiveInt, PositiveFloat, field_validator, Field

from musify.exception import MusifyValueError
from musify.models import MusifyRootModel
from musify.models._base import _AttributeModel


@total_ordering
class Length(MusifyRootModel[PositiveInt | PositiveFloat]):
    # noinspection PyNestedDecorators
    @field_validator("root", mode="before", check_fields=True)
    @staticmethod
    def _convert_numeric_representation_to_number(value: Any) -> str | int | float:
        if not isinstance(value, str):
            return value
        if re.match(r"^\d+(\.\d+)?$", value):  # already a number
            return float(value) if "." in value else int(value)

        factors = (24, 60, 60, 1)
        digits_split = value.split(":")
        digits = tuple(int(n.split(",")[0]) for n in digits_split)

        seconds = 0
        if "," in digits_split[-1]:  # add milliseconds if present
            number = digits_split[-1].split(",")[1]
            seconds += int(number) / (10 ** len(number))

        for i, digit in enumerate(reversed(digits), 1):  # convert to seconds
            seconds += digit * reduce(mul, factors[-i:], 1)

        return seconds

    @property
    def timedelta(self) -> timedelta:
        """Returns the length as a timedelta object."""
        return timedelta(seconds=int(self), milliseconds=int(float(self) % 1 * 1000))

    def __str__(self):
        hours = int(self) // 3600
        minutes = (int(self) % 3600) // 60
        seconds = int(self) % 60
        milliseconds = int(float(self) % 1 * 1000)

        length = f"{minutes:02d}:{seconds:02d}"
        if hours:
            length = f"{hours}:{length}"
        if milliseconds:
            length += f".{milliseconds:03d}"
        return length

    def __int__(self):
        return int(self.root)

    def __float__(self):
        return float(self.root)

    def __eq__(self, other: Any) -> bool:
        match other:
            case Length():
                return self.root == other.root
            case int() | float():
                return float(self.root) == float(other)
            case str():
                try:
                    other_length = Length(other)
                    return self.root == other_length.root
                except MusifyValueError:
                    return False
            case _:
                return False

    def __lt__(self, other: Any) -> bool:
        match other:
            case Length():
                return self.root < other.root
            case int() | float():
                return float(self.root) < float(other)
            case str():
                try:
                    other_length = Length(other)
                    return self.root < other_length.root
                except MusifyValueError:
                    return NotImplemented
            case _:
                return NotImplemented


class HasLength(_AttributeModel):
    """Represents a resource that has a length."""
    length: Length | None = Field(
        description="The length of this resource.",
        default=None,
    )


HasLength.__tag_fields__ = frozenset({*HasLength.model_fields})
