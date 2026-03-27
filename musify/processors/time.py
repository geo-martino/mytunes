"""
Processor that converts representations of time units to python time objects.
"""
from datetime import timedelta
from typing import Any

from dateutil.relativedelta import relativedelta

from musify.printer import PrettyPrinter
from musify.processors.base import DynamicProcessor, dynamicprocessormethod


class TimeMapper(DynamicProcessor, PrettyPrinter):
    """Map of time character representation to it unit conversion from seconds"""

    __slots__ = ()

    @classmethod
    def _processor_method_fmt(cls, name: str) -> str:
        return name.casefold().strip()[0] if not name.startswith("min") else name

    def __init__(self, func: str):
        super().__init__()
        self._set_processor_name(func)

    def __call__(self, *args, **kwargs) -> timedelta | relativedelta:
        return self.map(*args, **kwargs)

    def map(self, value: Any):
        """Run the mapping function"""
        return super().__call__(value)

    @dynamicprocessormethod
    def seconds(self, value: Any) -> timedelta:
        """Map given ``value`` in seconds to :py:class:`timedelta`"""
        return timedelta(seconds=int(value))

    @dynamicprocessormethod("min")
    def minutes(self, value: Any) -> timedelta:
        """Map given ``value`` in minutes to :py:class:`timedelta`"""
        return timedelta(minutes=int(value))

    @dynamicprocessormethod
    def hours(self, value: Any) -> timedelta:
        """Map given ``value`` in hours to :py:class:`timedelta`"""
        return timedelta(hours=int(value))

    @dynamicprocessormethod
    def days(self, value: Any) -> timedelta:
        """Map given ``value`` in days to :py:class:`timedelta`"""
        return timedelta(days=int(value))

    @dynamicprocessormethod
    def weeks(self, value: Any) -> timedelta:
        """Map given ``value`` in weeks to :py:class:`timedelta`"""
        return timedelta(weeks=int(value))

    @dynamicprocessormethod
    def months(self, value: Any) -> relativedelta:
        """Map given ``value`` in months to :py:class:`timedelta`"""
        return relativedelta(months=int(value))

    def as_dict(self) -> dict[str, Any]:
        return {"function": self._processor_name}
