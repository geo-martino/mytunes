from __future__ import annotations

from contextlib import suppress
from datetime import date, datetime
from functools import total_ordering
from typing import Annotated, Any, Self

from pydantic import PositiveInt, Field, model_validator, TypeAdapter, NonNegativeInt, ValidationError

from mytunes._models.metadata import TagAttribute, Attribute
from .._base.attribute import AttributeModel
from ...exception import MyTunesValidationError

_DATA_ADAPTER = TypeAdapter[date](date)


@total_ordering
class SparseDate(AttributeModel):
    """
    A sparse date represents a date which may not have all parts to make up a full date.

    This allows for defining a date as just the year, or just the year and month,
    while also allowing for a full date definition of year, month, and day.
    """
    year: Annotated[PositiveInt, TagAttribute()] = Field(
        description="The year.",
    )
    month: Annotated[int, TagAttribute()] | None = Field(
        description="The month.",
        default=None,
        ge=1,
        le=12,
    )
    day: Annotated[int, TagAttribute()] | None = Field(
        description="The day.",
        default=None,
        ge=1,
        le=31,
    )

    @model_validator(mode="before")
    @classmethod
    def _from_date[T](cls, data: T | Any) -> T | dict[str, Any]:
        with suppress(ValueError):
            dt = _DATA_ADAPTER.validate_python(data)
            return dict(year=dt.year, month=dt.month, day=dt.day)
        return data

    @model_validator(mode="before")
    @classmethod
    def _from_string[T](cls, data: T | str) -> T | dict[str, Any]:
        if not isinstance(data, str):
            return data

        value = iter(data.split("-"))
        return dict(year=next(value, None), month=next(value, None), day=next(value, None))

    @model_validator(mode="after")
    def _validate_month_not_set_when_day_set(self) -> Self:
        if self.month is None and self.day is not None:
            raise MyTunesValidationError("Cannot set day when month is not set.")
        return self

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
        return hash((self.year, self.month or 1, self.day or 1))

    def __eq__(self, other):
        if self is other:
            return True
        if isinstance(other, date):
            return self.date == other
        if isinstance(other, str):
            try:
                dt = TypeAdapter(date).validate_python(other)
                return self.__eq__(dt)
            except ValidationError:
                return False

        return super().__eq__(other)

    def __lt__(self, other: Any) -> bool:
        def _sort_key(item: Any) -> tuple[int, int, int] | None:
            match item:
                case SparseDate():
                    return item.year, item.month or 1, item.day or 1
                case date():
                    return item.year, item.month, item.day
                case str():
                    try:
                        dt = SparseDate.model_validate(other)
                        return _sort_key(dt)
                    except ValidationError:
                        return None
                case _:
                    return None

        self_key = _sort_key(self)
        other_key = _sort_key(other)
        return self_key is not None and other_key is not None and self_key < other_key


class HasReleaseDate(AttributeModel):
    """Represents a resource that has an associated release date."""
    released_at: Annotated[SparseDate | None, Attribute()] = Field(
        description="The date this resource was released.",
        default=None,
    )


class HasAddedDate(AttributeModel):
    """Represents a resource that has an associated added date."""
    added_at: Annotated[datetime | None, Attribute()] = Field(
        description="The date this resource was added to the collection.",
        default=None,
    )


class HasPlayedDate(AttributeModel):
    """Represents a resource that has an associated played date."""
    last_played_at: Annotated[datetime | None, Attribute()] = Field(
        description="The date this resource was last played.",
        default=None,
    )
    play_count: Annotated[NonNegativeInt | None, Attribute()] = Field(
        description="The number of times this resource has been played.",
        default=None,
    )
