from __future__ import annotations

from functools import total_ordering
from typing import Any, Self, ClassVar

from pydantic import PositiveInt, Field, model_validator, NonNegativeInt, ModelWrapValidatorHandler

from musify.exception import MusifyValueError
from musify.models._base import AttributeModel, AttributeResource


@total_ordering
class Position(AttributeModel):
    """Represents the index position of a resource within a parent resource."""
    __tag_attributes__ = ("number", "total")

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
    zero_fill: bool | NonNegativeInt = Field(
        description="Number of digits to zero-fill each number when rendering the position as a string.",
        default=False,
    )

    # noinspection PyNestedDecorators
    @model_validator(mode="wrap")
    @classmethod
    def _from_number(cls, value: int | float, handler: ModelWrapValidatorHandler[Self]) -> Self:
        if not isinstance(value, int | float):
            return handler(value)

        data = dict(number=int(value))
        return handler(data)

    # noinspection PyNestedDecorators
    @model_validator(mode="wrap")
    @classmethod
    def _from_numbers(cls, value: tuple | list, handler: ModelWrapValidatorHandler[Self]) -> Self:
        if not isinstance(value, tuple | list):
            return handler(value)

        numbers = iter(value)
        data = dict(number=next(numbers, None), total=next(numbers, None))
        return handler(data)

    # noinspection PyNestedDecorators
    @model_validator(mode="wrap")
    @classmethod
    def _from_string(cls, value: str, handler: ModelWrapValidatorHandler[Self]) -> Self:
        if not isinstance(value, str):
            return handler(value)

        numbers = iter(value.split(cls.sep))
        data = dict(number=next(numbers), total=next(numbers, None))
        return handler(data)

    @model_validator(mode="after")
    def _validate_position_is_less_than_total(self) -> Self:
        if self.number is None or self.total is None:
            return self

        if self.number > self.total:
            raise MusifyValueError("Start position cannot be greater than end position.")
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

    def __hash__(self) -> int:
        return hash((self.number or 0, self.total or 0, self.zero_fill))

    def __eq__(self, other: Any) -> bool:
        return other is not None and self.number == int(other)

    def __lt__(self, other: Any) -> bool:
        return other is not None and self.number < int(other)


class HasTrackPosition(AttributeResource):
    """Represents a resource that has a track position."""
    track: Position | None = Field(
        description="The position in the collection that this track is featured on.",
        default=None,
    )


class HasDiscPosition(AttributeResource):
    """Represents a resource that has a disc position."""
    disc: Position | None = Field(
        description="The position of the disc in the collection that this resource is featured on.",
        default=None,
    )
