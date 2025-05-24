from __future__ import annotations

from typing import Any, Self, ClassVar

from pydantic import PositiveInt, Field, model_validator, model_serializer

from musify.exception import MusifyValueError
from musify.model import MusifyModel


class Position(MusifyModel):
    """Represents the index position of a resource within a parent resource."""
    #: The separator to use when parsing a string representation of the position.
    sep: ClassVar[str] = "/"

    number: PositiveInt | None = Field(
        description="The index position of the resource within the parent resource.",
        default=None,
    )
    total: PositiveInt | None = Field(
        description="The total number of resources in the parent resource.",
        default=None,
    )

    # noinspection PyNestedDecorators
    @model_validator(mode="before")
    @staticmethod
    def _from_number[T](value: T) -> T | dict[str, Any]:
        if not isinstance(value, int | float):
            return value
        return dict(number=int(value))

    # noinspection PyNestedDecorators
    @model_validator(mode="before")
    @staticmethod
    def _from_numbers[T](value: T) -> T | dict[str, Any]:
        if not isinstance(value, tuple | list):
            return value

        numbers = iter(value)
        return dict(number=next(numbers, None), total=next(numbers, None))

    # noinspection PyNestedDecorators
    @model_validator(mode="before")
    @classmethod
    def _from_string[T](cls, value: T) -> T | dict[str, Any]:
        if not isinstance(value, str):
            return value
        numbers = iter(value.split(cls.sep))
        return dict(number=next(numbers), total=next(numbers, None))

    @model_serializer
    def _serialize_string(self) -> str | None:
        if self.number is None:
            return None
        if self.total is None:
            return str(self.number)
        return f"{self.number}{self.sep}{self.total}"

    @model_validator(mode="after")
    def _validate_position_is_less_than_total(self) -> Self:
        if self.number is None or self.total is None:
            return self

        if self.number > self.total:
            raise MusifyValueError("Start position cannot be greater than end position.")
        return self
