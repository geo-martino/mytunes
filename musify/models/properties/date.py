from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Self

from pydantic import PositiveInt, Field, model_validator, TypeAdapter, NonNegativeInt, ModelWrapValidatorHandler

from musify.models._base import AttributeResource, AttributeModel


class SparseDate(AttributeModel):
    """
    A sparse date represents a date which may not have all parts to make up a full date.

    This allows for defining a date as just the year, or just the year and month,
    while also allowing for a full date definition of year, month, and day.
    """
    __tag_attributes__ = ("year", "month", "day")

    year: PositiveInt = Field(
        description="The year.",
    )
    month: Annotated[int, Field(ge=1, le=12)] | None = Field(
        description="The month.",
        default=None,
    )
    day: Annotated[int, Field(ge=1, le=31)] | None = Field(
        description="The day.",
        default=None,
    )

    # noinspection PyNestedDecorators
    @model_validator(mode="wrap")
    @staticmethod
    def _from_date(value: Any, handler: ModelWrapValidatorHandler[Self]) -> Self:
        try:
            dt = TypeAdapter(date).validate_python(value)
            data = dict(year=dt.year, month=dt.month, day=dt.day)
            return handler(data)
        except ValueError:
            return handler(value)

    # noinspection PyNestedDecorators
    @model_validator(mode="wrap")
    @staticmethod
    def _from_string(value: str, handler: ModelWrapValidatorHandler[Self]) -> Self:
        if not isinstance(value, str):
            return handler(value)

        value = iter(value.split("-"))
        data = dict(year=next(value, None), month=next(value, None), day=next(value, None))
        return handler(data)

    @property
    def date(self) -> date | None:
        """A :py:class:`date` object representing the full date definition if available."""
        if self.year and self.month and self.day:
            return date(self.year, self.month, self.day)

    def __str__(self) -> str:
        if self.month and self.day:
            return self.date.isoformat()
        elif self.month and not self.day:
            return f"{self.year:04d}-{self.month:02d}"
        return str(self.year)

    def __hash__(self) -> int:
        return hash((self.year, self.month or 0, self.day or 0))

    def __eq__(self, other):
        if self is other:
            return True
        if isinstance(other, date):
            return self.date == other
        if isinstance(other, str):
            try:
                dt = TypeAdapter(date).validate_python(other)
                return self.__eq__(dt)
            except ValueError:
                return False

        return super().__eq__(other)


class HasReleaseDate(AttributeResource):
    """Represents a resource that has an associated release date."""
    released_at: SparseDate | None = Field(
        description="The date this resource was released.",
        default=None,
    )


class HasAddedDate(AttributeResource):
    """Represents a resource that has an associated added date."""
    added_at: datetime | None = Field(
        description="The date this resource was added to the collection.",
        default=None,
    )


class HasPlayedDate(AttributeResource):
    """Represents a resource that has an associated played date."""
    last_played_at: datetime | None = Field(
        description="The date this resource was last played.",
        default=None,
    )
    play_count: NonNegativeInt | None = Field(
        description="The number of times this resource has been played.",
        default=None,
    )
