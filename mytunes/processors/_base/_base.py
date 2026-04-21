"""
Base classes for all processors in this module. Also contains decorators for use in implementations.
"""
from collections.abc import Iterable
from typing import Any

from mytunes.core.properties.name import HasName
from mytunes.core.properties.uri import HasURI

from ..._base import BaseModel


class Processor(BaseModel):
    """Generic base class for processors"""
    @classmethod
    def _format_item_message(
            cls,
            method: str,
            item: Any,
            messages: str | Iterable,
            pad: str = " ",
    ) -> str:
        if isinstance(messages, str):
            messages = (messages,)

        title = cls._get_item_log_value(item)
        header = f"{pad[0] * 3} {method.upper():<7}: {title}"
        return "|" + " | ".join([header] + list(map(str, messages)))

    @staticmethod
    def _get_item_log_value(item: Any) -> str:
        match item:
            case str() as value:
                return value
            case HasURI() as it if it.has_uri:
                return str(it.uri)
            case HasName() as it:
                return str(it.name)
            case _:
                return "- UNKNOWN -"
