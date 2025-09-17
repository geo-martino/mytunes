from __future__ import annotations

from typing import Any, Self, ClassVar

from pydantic import PositiveInt, Field, model_validator, NonNegativeInt

from musify.exception import MusifyValueError
from musify.models import MusifyModel
from musify.models._base import _AttributeModel


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
    zero_fill: NonNegativeInt = Field(
        description="Number of digits to zero-fill each number when rendering the position as a string.",
        default=0,
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
        return self.sep.join(str(val).zfill(self.zero_fill) for val in self.numbers)

    def __hash__(self) -> int:
        return hash((self.number or 0, self.total or 0, self.zero_fill))


class HasTrackPosition(_AttributeModel):
    """Represents a resource that has a track position."""
    track: Position | None = Field(
        description="The position in the collection that this track is featured on.",
        default=None,
    )

    @property
    def track_number(self) -> int | None:
        """The track number."""
        return self.track.number if self.track else None

    @property
    def track_total(self) -> int | None:
        """The total number of tracks."""
        return self.track.total if self.track else None


HasTrackPosition.__tag_fields__ = frozenset({
    *HasTrackPosition.model_fields,
    *{name for name, method in vars(HasTrackPosition).items() if isinstance(method, property)}
})


class HasDiscPosition(_AttributeModel):
    """Represents a resource that has a disc position."""
    disc: Position | None = Field(
        description="The position of the disc in the collection that this resource is featured on.",
        default=None,
    )

    @property
    def disc_number(self) -> int | None:
        """The disc number."""
        return self.disc.number if self.disc else None

    @property
    def disc_total(self) -> int | None:
        """The total number of discs."""
        return self.disc.total if self.disc else None


HasDiscPosition.__tag_fields__ = frozenset({
    *HasDiscPosition.model_fields,
    *{name for name, method in vars(HasDiscPosition).items() if isinstance(method, property)}
})
