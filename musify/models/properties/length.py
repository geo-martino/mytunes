from __future__ import annotations

import re
from datetime import timedelta
from functools import reduce, total_ordering
from operator import mul
from typing import Any

from pydantic import NonNegativeInt, NonNegativeFloat, field_validator, Field

from musify.models._base import MusifyRootModel, AttributeResource


@total_ordering
class Length(MusifyRootModel[NonNegativeInt | NonNegativeFloat]):
    # noinspection PyNestedDecorators
    @field_validator("root", mode="before", check_fields=True)
    @staticmethod
    def _convert_numeric_representation_to_number[T: str](value: T) -> T | int | float:
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

    def __hash__(self) -> int:
        return hash(self.root)

    def __eq__(self, other: Any) -> bool:
        return other is not None and self.root == float(other)

    def __lt__(self, other: Any) -> bool:
        return other is not None and self.root < float(other)

    def __add__(self, other: Any) -> Length:
        return self.model_validate(self.root + float(other))

    def __sub__(self, other: Any) -> Length:
        return self.model_validate(self.root - float(other))

    def __mul__(self, other: Any) -> Length:
        return self.model_validate(self.root * float(other))

    def __truediv__(self, other: Any) -> Length:
        return self.model_validate(self.root / float(other))


class HasLength(AttributeResource):
    """Represents a resource that has a length."""
    length: Length | None = Field(
        description="The length of this resource.",
        default=None,
    )
