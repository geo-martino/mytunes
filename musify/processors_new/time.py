"""
Processor that converts representations of time units to python time objects.
"""
import re
from datetime import timedelta, datetime, date
from typing import Any, Annotated

from dateutil.relativedelta import relativedelta
from pydantic import field_validator, Field, model_validator
from pydantic.alias_generators import to_snake

from musify._types import LowerSnakeCase
from musify.processors_new import DynamicProcessor, dynamicprocessormethod


class TimeMapper(DynamicProcessor):
    """Map of time character representation to enable simple to use time delta conversion."""

    unit: LowerSnakeCase = Field(
        description="The time unit to add/subtract.",
    )
    amount: Annotated[int, Field(gt=0)] = Field(
        description="The amount of the given unit to add/subtract.",
    )
    add: bool = Field(
        description="When true, add the time delta to the given datetime, otherwise subtract it.",
        default=False
    )

    @property
    def _processor_name(self) -> str | None:
        return self.unit

    # noinspection PyNestedDecorators
    @model_validator(mode="before")
    @classmethod
    def _from_key(cls, value: str) -> Any:
        if not isinstance(value, str) or not re.match(r"^[-+]?\d+\D+$", value):
            return value
        return dict(
            unit=cls._extract_unit_from_key(value),
            amount=cls._extract_amount_from_key(value),
            add=cls._extract_sign_from_key(value),
        )

    # noinspection PyNestedDecorators
    @field_validator("unit", mode="before", check_fields=True)
    @staticmethod
    def _extract_unit_from_key(value: str) -> Any:
        if not isinstance(value, str) or not re.match(r"^[-+]?\d+\D+$", value):
            return value
        return re.match(r"^[-+]?\d+(\D+)$", value).group(1)

    @field_validator("unit", mode="before", check_fields=True)
    @staticmethod
    def _clean_processor_name(name: str) -> str:
        return to_snake(name).replace(" ", "_").strip("_")

    # noinspection PyNestedDecorators
    @model_validator(mode="after")
    def _map_unit_value(self) -> Any:
        unit = self._clean_processor_name(self.__processor_method_map__[self.unit])
        if unit != self.unit:
            self.unit = unit

        return self

    # noinspection PyNestedDecorators
    @field_validator("amount", mode="before", check_fields=True)
    @staticmethod
    def _extract_amount_from_key(value: str) -> Any:
        if not isinstance(value, str) or not re.match(r"^[-+]?\d+\D+$", value):
            return value
        return re.match(r"^[-+]?(\d+)\D+$", value).group(1)

    # noinspection PyNestedDecorators
    @field_validator("add", mode="before", check_fields=True)
    @staticmethod
    def _extract_sign_from_key(value: str) -> Any:
        if not isinstance(value, str) or not re.match(r"^[-+]?\d+\D+$", value):
            return value
        return value.startswith("+")

    @property
    def key(self) -> str:
        """A string representation of the timedelta."""
        return f"{'+' if self.add else '-'}{self.amount}{self.unit}"

    # noinspection PyTypeChecker
    @key.setter
    def key(self, value: str) -> None:
        self.unit = value
        self.amount = value
        self.add = value

    def __str__(self) -> str:
        return self.key

    def __call__[T: date | datetime](self, value: T) -> T:
        return self.apply(value)

    def apply[T: date | datetime](self, value: T) -> T:
        """Apply the time delta to the given date or datetime."""
        return super().__call__(value)

    @dynamicprocessormethod("s", "sec", "secs", "second")
    def _seconds[T: date | datetime](self, value: T) -> T:
        delta = timedelta(seconds=self.amount)
        return value + delta if self.add else value - delta

    @dynamicprocessormethod("m", "min", "mins", "minute")
    def _minutes[T: date | datetime](self, value: T) -> T:
        delta = timedelta(minutes=self.amount)
        return value + delta if self.add else value - delta

    @dynamicprocessormethod("h", "hr", "hrs", "hour")
    def _hours[T: date | datetime](self, value: T) -> T:
        delta = timedelta(hours=self.amount)
        return value + delta if self.add else value - delta

    @dynamicprocessormethod("d", "day", "days")
    def _days[T: date | datetime](self, value: T) -> T:
        delta = timedelta(days=self.amount)
        return value + delta if self.add else value - delta

    @dynamicprocessormethod("w", "wk", "wks", "week")
    def _weeks[T: date | datetime](self, value: T) -> T:
        delta = relativedelta(weeks=self.amount)
        return value + delta if self.add else value - delta

    @dynamicprocessormethod("mon", "mons", "mth", "mths", "month")
    def _months[T: date | datetime](self, value: T) -> T:
        delta = relativedelta(months=self.amount)
        return value + delta if self.add else value - delta
