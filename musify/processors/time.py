"""
Processor that converts representations of time units to python time objects.
"""
import re
from datetime import timedelta, datetime, date
from typing import Any, Annotated, Self, final

from dateutil.relativedelta import relativedelta
from pydantic import field_validator, Field, model_validator, ModelWrapValidatorHandler
from pydantic.alias_generators import to_snake

from musify._types import LowerSnakeCase
from ._base.dynamic import DynamicProcessor, ProcessorAttribute, processormethod


@final
class TimeMapper(DynamicProcessor):
    """Map of time character representation to enable simple to use time delta conversion."""
    __final__ = True

    unit: Annotated[
        LowerSnakeCase,
        ProcessorAttribute(cleaner=lambda x: to_snake(x).replace(" ", "_").strip("_")),
    ] = Field(
        description="The time unit to add/subtract.",
    )
    amount: Annotated[int, Field(gt=0)] = Field(
        description="The amount of the given unit to add/subtract.",
    )
    add: bool = Field(
        description="When true, add the time delta to the given datetime, otherwise subtract it.",
        default=False
    )

    @model_validator(mode="before")
    def _from_key[T](cls, data: T | str) -> T | dict[str, Any]:
        if not isinstance(data, str) or not re.match(r"^[-+]?\d+\D+$", data):
            return data

        data = dict(
            unit=cls._extract_unit_from_key(data),
            amount=cls._extract_amount_from_key(data),
            add=cls._extract_sign_from_key(data),
        )
        return data

    @field_validator("unit", mode="before", check_fields=True)
    @staticmethod
    def _extract_unit_from_key(value: str) -> str:
        if not isinstance(value, str) or not re.match(r"^[-+]?\d+\D+$", value):
            return value
        return re.match(r"^[-+]?\d+(\D+)$", value).group(1)

    @field_validator("amount", mode="before", check_fields=True)
    @staticmethod
    def _extract_amount_from_key(value: str) -> str:
        if not isinstance(value, str) or not re.match(r"^[-+]?\d+\D+$", value):
            return value
        return re.match(r"^[-+]?(\d+)\D+$", value).group(1)

    @field_validator("add", mode="before", check_fields=True)
    @staticmethod
    def _extract_sign_from_key[T: str](value: T) -> T | bool:
        if not isinstance(value, str) or not re.match(r"^[-+]?\d+\D+$", value):
            return value
        return value.startswith("+")

    @model_validator(mode="after")
    def _map_processor_value(self) -> Any:
        field_name: str = type(self).processor_field_name
        method_name: str = self._processor_method_name

        field_value = getattr(self, field_name)
        clean_value = type(self).get_clean_processor_name(method_name)
        if clean_value != field_value:
            self.__dict__[field_name] = clean_value

        return self

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
        return str(self.key)

    def __hash__(self) -> int:
        return hash(self.key)

    def apply[T: date | datetime](self, value: T) -> T:
        """Apply the time delta to the given date or datetime."""
        return self._processor_method(value)

    @processormethod("s", "sec", "secs", "second")
    def _seconds[T: date | datetime](self, value: T) -> T:
        delta = timedelta(seconds=self.amount)
        return value + delta if self.add else value - delta

    @processormethod("m", "min", "mins", "minute")
    def _minutes[T: date | datetime](self, value: T) -> T:
        delta = timedelta(minutes=self.amount)
        return value + delta if self.add else value - delta

    @processormethod("h", "hr", "hrs", "hour")
    def _hours[T: date | datetime](self, value: T) -> T:
        delta = timedelta(hours=self.amount)
        return value + delta if self.add else value - delta

    @processormethod("d", "day", "days")
    def _days[T: date | datetime](self, value: T) -> T:
        delta = timedelta(days=self.amount)
        return value + delta if self.add else value - delta

    @processormethod("w", "wk", "wks", "week")
    def _weeks[T: date | datetime](self, value: T) -> T:
        delta = relativedelta(weeks=self.amount)
        return value + delta if self.add else value - delta

    @processormethod("mon", "mons", "mth", "mths", "month")
    def _months[T: date | datetime](self, value: T) -> T:
        delta = relativedelta(months=self.amount)
        return value + delta if self.add else value - delta
