from __future__ import annotations

from functools import total_ordering
from typing import Any, Self, ClassVar, Annotated

from aiorequestful.types import Number
from pydantic import PositiveInt, Field, model_validator, NonNegativeInt

from mytunes.exception import MyTunesValidationError
from ..._base.attribute import AttributeModel, Attribute, TagAttribute


@total_ordering
class Position(AttributeModel):
    """Represents the index position of a resource within a parent resource."""
    #: The separator to use when parsing a string representation of the position.
    sep: ClassVar[str] = "/"

    number: Annotated[PositiveInt | None, TagAttribute()] = Field(
        description="The index position of the resource within the parent resource.",
        default=None,
    )
    total: Annotated[PositiveInt | None, TagAttribute()] = Field(
        description="The total number of resources in the parent resource.",
        default=None,
    )
    zero_fill: Annotated[bool | NonNegativeInt, Attribute()] = Field(
        description=(
            "Number of digits to zero-fill each number when rendering the position as a string. ",
            "Alternatively if true, apply zero-fill to the number based on the number of digits of the total."
        ),
        default=False,
    )

    @model_validator(mode="before")
    @classmethod
    def _from_number[T](cls, data: T | Number) -> T | dict[str, Any]:
        if not isinstance(data, int | float):
            return data

        return dict(number=int(data))

    @model_validator(mode="before")
    @classmethod
    def _from_numbers[T](cls, data: T | tuple | list) -> T | dict[str, Any]:
        if not isinstance(data, tuple | list):
            return data

        numbers = iter(data)
        return dict(number=next(numbers, None), total=next(numbers, None))

    @model_validator(mode="before")
    @classmethod
    def _from_strin[T](cls, data: T | str) -> T | dict[str, Any]:
        if not isinstance(data, str):
            return data

        numbers = iter(data.split(cls.sep))
        return dict(number=next(numbers), total=next(numbers, None))

    @model_validator(mode="after")
    def _validate_position_is_less_than_total(self) -> Self:
        if self.number is None or self.total is None:
            return self

        if self.number > self.total:
            raise MyTunesValidationError("Start position cannot be greater than end position.")
        return self

    @property
    def numbers(self) -> tuple[()] | tuple[int] | tuple[int, int]:
        """Get the numbers in the position as a tuple."""
        if self.number is None:
            return ()
        elif self.total is None:
            return (self.number,)
        return self.number, self.total

    def __str__(self) -> str:
        zero_fill = self.zero_fill
        if isinstance(zero_fill, bool):
            zero_fill = len(str(self.total)) if zero_fill and self.total is not None else 0
        return self.sep.join(str(val).zfill(zero_fill) for val in self.numbers)

    def __int__(self):
        return self.number

    def __eq__(self, other: Any) -> bool:
        return other is not None and self.number == int(other)

    def __lt__(self, other: Any) -> bool:
        return other is not None and self.number < int(other)


class HasTrackPosition(AttributeModel):
    """Represents a model that has a track position."""
    track: Annotated[Position | None, Attribute()] = Field(
        description="The position in the collection that this track is featured on.",
        default=None,
    )


class HasDiscPosition(AttributeModel):
    """Represents a model that has a disc position."""
    disc: Annotated[Position | None, Attribute()] = Field(
        description="The position of the disc in the collection that this resource is featured on.",
        default=None,
    )
