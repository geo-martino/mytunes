from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from pydantic import PositiveInt, Field, model_validator, TypeAdapter, model_serializer

from musify.model import MusifyModel
from musify.model._base import _AttributeModel


class SparseDate(MusifyModel):
    """
    A sparse date represents a date which may not have all parts to make up a full date.

    This allows for defining a date as just the year, or just the year and month,
    while also allowing for a full date definition of year, month, and day.
    """
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
    @model_validator(mode="before")
    @staticmethod
    def _from_date[T](value: T) -> T | dict[str, Any]:
        try:
            dt = TypeAdapter(date).validate_python(value)
            return dict(year=dt.year, month=dt.month, day=dt.day)
        except ValueError:
            pass

        return value

    # noinspection PyNestedDecorators
    @model_validator(mode="before")
    @staticmethod
    def _from_string[T](value: T) -> T | dict[str, Any]:
        if not isinstance(value, str):
            return value

        value = iter(value.split("-"))
        return dict(year=next(value, None), month=next(value, None), day=next(value, None))

    @model_serializer
    def _serialize_string(self) -> str:
        if self.month and self.day:
            return self.date.isoformat()
        elif self.month and not self.day:
            return f"{self.year:04d}-{self.month:02d}"
        return str(self.year)

    @property
    def date(self) -> date | None:
        """A :py:class:`date` object representing the full date definition if available."""
        if self.year and self.month and self.day:
            return date(self.year, self.month, self.day)

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


class HasReleaseDate(_AttributeModel):
    """Represents a resource that has an associated release date."""
    released_at: SparseDate | None = Field(
        description="The date this resource was released.",
        default=None,
    )
