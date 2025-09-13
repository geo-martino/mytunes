from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

from pydantic import PositiveInt, PositiveFloat, field_validator, Field

from musify.exception import MusifyValueError
from musify.models import MusifyRootModel
from musify.models._base import _AttributeModel


class Length(MusifyRootModel[PositiveInt | PositiveFloat]):
    # noinspection PyNestedDecorators
    @field_validator("root", mode="before", check_fields=True)
    @staticmethod
    def _convert_numeric_representation_to_number(value: Any) -> str | int | float:
        if not isinstance(value, str):
            return value

        # skip string values that are purely numeric, let pydantic handle them
        if re.match(r"^\d+$", value) or re.match(r"^\d+\.\d+$", value):
            return value

        if matches := re.match(r"^(\d{2}):(\d{2})(?:$|\.\d+$)", value):
            hours = 0
            minutes, seconds = tuple(map(int, matches.groups()))
        elif matches := re.match(r"^(\d+):(\d{2}):(\d{2})(?:$|\.\d+$)", value):
            hours, minutes, seconds = tuple(map(int, matches.groups()))
        else:
            raise MusifyValueError(f"Invalid length format: {value}")

        total_seconds = seconds + (minutes * 60) + (hours * 3600)

        if matches := re.match(r"^.*\.(\d+)$", value):
            milliseconds = int(matches.group(1)) / (10 ** len(matches.group(1)))
            return float(total_seconds + milliseconds)

        return total_seconds

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


class HasLength(_AttributeModel):
    """Represents a resource that has a length."""
    length: Length | None = Field(
        description="The length of this resource.",
        default=None,
    )
