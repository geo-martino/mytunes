import re
import textwrap
from collections.abc import Iterable, Mapping, Collection, Callable, Sequence
from typing import ClassVar, Self, Any, Literal

from pydantic import ConfigDict, Field, PositiveInt
from pydantic.dataclasses import dataclass
from tabulate import tabulate
from termcolor import colored

from musify._types import StrippedString
from musify.exception import MusifyTypeError
from musify.models import BaseModel
from musify.models.metadata import Attribute


@dataclass(config=ConfigDict(frozen=True))
class LogFormatter[T](Attribute):
    """Metadata for logging a field's value."""
    width: PositiveInt | None = Field(
        description="The alignment width for the field's value in logs.",
        default=None,
    )
    alignment: Literal["left", "right", "centre"] | None = Field(
        description="The alignment for the field's value in logs.",
        default=None,
    )
    max_width: PositiveInt | None = Field(
        description=(
            "The max permitted width for the field's value in logs, after which it will be truncated with an ellipsis."
        ),
        default=None,
        ge=3,
    )

    colour: StrippedString | None = Field(
        description="The colour to apply to the field's value in logs.",
        default=None,
    )
    colour_attributes: Sequence[StrippedString] = Field(
        description="The colour attributes to apply to the field's value in logs.",
        default_factory=tuple,
    )
    condition: Callable[[T], bool] = Field(
        description="Only log this field when this condition is True.",
        default=lambda _: True,
    )

    def get_value(self, value: T | None = None, pretty: bool = True) -> str | None:
        """Get the given log value if the value is valid."""
        if value is not None and not self.condition(value):
            return None

        value = str(value) if value is not None else ""
        if not pretty:
            return value

        value = self._align_value(value)
        return colored(value, color=self.colour, attrs=self.colour_attributes)

    def _align_value(self, value: str) -> str:
        """Align the given log value according to the alignment and width."""
        if self.max_width is not None and len(value) > self.max_width:
            value = textwrap.shorten(value, self.max_width, placeholder="...")

        if self.width is None or self.alignment is None:
            return value

        match self.alignment:
            case "left":
                return f"{value:<{self.width}}"
            case "right":
                return f"{value:>{self.width}}"
            case "centre":
                return f"{value:^{self.width}}"


@dataclass(config=ConfigDict(frozen=True))
class LenLogFormatter(LogFormatter[int]):
    """Metadata for logging the total length of a field's value."""
    def get_value(self, value: int | Collection | None = None, pretty: bool = True) -> str | None:
        return super().get_value(self._get_length_value(value), pretty=pretty)

    @staticmethod
    def _get_length_value(value: Any) -> int | None:
        match value:
            case str() as value_str if value_str.isdigit():
                return int(value_str)
            case int() | float():
                return int(value)
            case Collection() if not isinstance(value, str):
                return len(value)
            case _:
                raise MusifyTypeError(f"Value must be an int or a collection, got {type(value)}")


class Result(BaseModel):
    """Stores the results of an operation"""
    model_config = ConfigDict(frozen=True)

    _table_format: ClassVar[str] = "orgtbl"
    _header_formatter: ClassVar[LogFormatter] = LogFormatter(
        colour="cyan",
        colour_attributes=["bold"],
    )
    _key_formatter: ClassVar[LogFormatter] = LogFormatter(
        max_width=40,
        colour="white",
        colour_attributes=["bold"],
    )
    _name_formatter: ClassVar[LogFormatter] = LogFormatter(
        colour="white",
    )

    @classmethod
    def generate_table(cls, results: Mapping[str | None, Self | None], header: str = None) -> str:
        """Generate a formatted table of stats for multiple results"""
        # take key when not a Result to allow for separating lines
        rows = [result.generate_log(key) if isinstance(result, Result) else key for key, result in results.items()]
        col_count = max(map(len, rows)) if rows else 0
        table = tabulate(
            rows,
            tablefmt=cls._table_format,
            colalign=("left", *["right"] * max(0, col_count - 1)),
        )
        table = re.sub(r"\| +\|", "|", table)
        table = re.sub(r"\| +\|", "|", table)

        if header:
            table = cls._header_formatter.get_value(header) + ":\n" + table

        return table

    def generate_log(self, key: str | None = None) -> tuple[str, ...]:
        """Generate a log of stats for this result"""
        row = []

        if key:
            row.append(self._key_formatter.get_value(key))

        for field_name, (_, metadata) in self.__class__._metadata_fields.items():
            if not self._has_formatters(metadata):
                continue
            if (value := self._get_field_value(getattr(self, field_name), metadata)) is None:
                continue
            row.append(self._get_field_cell(value, field_name))

        return tuple(row)

    @staticmethod
    def _has_formatters(metadata: list[Any]) -> bool:
        return any(isinstance(meta, LogFormatter) for meta in metadata)

    @staticmethod
    def _get_field_value(value: Any, metadata: list[Any]) -> str | None:
        formatters = (meta for meta in metadata if isinstance(meta, LogFormatter))
        values = (formatter.get_value(value) for formatter in formatters)
        return next((v for v in values if v is not None), None)

    @classmethod
    def _get_field_cell(cls, value: str, name: str) -> str:
        return f"{value} {cls._name_formatter.get_value(name).replace("_", " ")}"


class CountResult(Result):
    """Same as Result but only with numeric fields which can be summed in a totals row."""
    _total_key_formatter: ClassVar[LogFormatter] = LogFormatter(
        max_width=40,
        colour="white",
        colour_attributes=["bold"],
    )

    @classmethod
    def generate_totals_log(cls, results: Iterable[Self]) -> tuple[str, ...]:
        """Generate a log of total stats for multiple results"""
        row = [cls._total_key_formatter.get_value("TOTAL")]

        for field_name, (_, metadata) in cls._metadata_fields.items():
            if not cls._has_formatters(metadata):
                continue

            total = sum(cls._get_field_count(getattr(result, field_name), metadata) for result in results)
            value = cls._get_field_value(total, metadata)
            row.append(cls._get_field_cell(value, field_name))

        return tuple(row)

    @staticmethod
    def _get_field_count(value: str, metadata: list[Any]) -> int:
        formatters = (attr for attr in metadata if isinstance(attr, LenLogFormatter))
        values = (formatter.get_value(value, pretty=False) for formatter in formatters)
        return next((int(v) for v in values if v is not None and v.lstrip("-").isdigit()), 0)


class TotalCountResult(CountResult):
    """
    Same as CountResult but with an additional total column at the end of the log
    for the sum of all numeric fields in a row.
    """
    _total_value_formatter: ClassVar[LogFormatter] = LenLogFormatter(
        width=6,
        alignment="right",
        colour="magenta",
        colour_attributes=["bold"],
    )

    def generate_log(self, key: str | None = None) -> tuple[str, ...]:
        row = list(super().generate_log(key))
        total = 0

        for field_name, (_, metadata) in self.__class__._metadata_fields.items():
            if not self._has_formatters(metadata):
                continue
            if (count := self._get_field_count(getattr(self, field_name), metadata)) is None:
                continue
            total += count

        row.append(self._get_total_cell(total))
        return tuple(row)

    @classmethod
    def generate_totals_log(cls, results: Iterable[Self]) -> tuple[str, ...]:
        row = list(super().generate_totals_log(results))
        total = 0

        for field_name, (_, metadata) in cls._metadata_fields.items():
            values = (cls._get_field_count(getattr(result, field_name), metadata) for result in results)
            total += sum(v for v in values if v is not None)

        row.append(cls._get_total_cell(total))
        return tuple(row)

    @classmethod
    def _get_total_cell(cls, total: int) -> str:
        value = cls._total_value_formatter.get_value(total)
        return cls._get_field_cell(value, "total")
