from __future__ import annotations

import re
from datetime import timedelta
from functools import reduce, total_ordering
from operator import mul
from typing import Annotated, Self

from pydantic import NonNegativeInt, NonNegativeFloat, field_validator, Field, model_validator

from mytunes._models import AttributeModel
from mytunes._models.collection import CollectionModel
from mytunes._models.metadata import Attribute
from mytunes._models.properties._core import NumberModel
from mytunes._types import Number


@total_ordering
class Length(NumberModel[NonNegativeInt | NonNegativeFloat]):
    @field_validator("root", mode="before", check_fields=True)
    @staticmethod
    def _convert_numeric_representation_to_number[T: str](value: T) -> T | Number:
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
            length = f"{hours:02d}:{length}"
        if milliseconds:
            length += f".{milliseconds:03d}"
        return length


class HasLength(AttributeModel):
    """Represents a resource that has a length."""
    length: Annotated[Length | None, Attribute()] = Field(
        description="The length of this resource.",
        default=None,
        frozen=True,
    )

    @model_validator(mode="after")
    def _set_length_from_items(self) -> Self:
        if not isinstance(self, CollectionModel):
            return self
        if not all(isinstance(item, HasLength) for item in self.items):
            return self

        self: CollectionModel | HasLength
        length = sum(float(item.length or 0) for item in self._items)
        if length != self.length and length > 0:
            self.__dict__["length"] = Length(length)

        return self
