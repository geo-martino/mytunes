"""
Core exceptions for the entire package.
"""
from typing import Any


class MusifyError(Exception):
    """Generic base class for all Musify-related errors"""


class MusifyKeyError(MusifyError, KeyError):
    """Exception raised for invalid keys."""


class MusifyValueError(MusifyError, ValueError):
    """Exception raised for invalid values."""


class MusifyTypeError(MusifyError, TypeError):
    """Exception raised for invalid types."""
    def __init__(self, kind: Any, message: str = "Invalid item type given"):
        self.message = message
        super().__init__(f"{self.message}: {kind}")


class MusifyAttributeError(MusifyError, AttributeError):
    """Exception raised for invalid attributes."""


class MusifyImportError(MusifyError, ImportError):
    """Exception raised for import errors, usually from missing modules."""


###########################################################################
## Enum errors
###########################################################################
class EnumError(MusifyError):
    """
    Exception raised for errors related to :py:class:`IntEnumModel` implementations.

    :param value: The value that caused the error.
    :param message: Explanation of the error.
    """

    def __init__(self, value: Any, message: str = "Could not find enum"):
        self.message = message
        super().__init__(f"{self.message}: {value}")


class FieldError(EnumError):
    """
    Exception raised for errors related to :py:class:`Field` enums.

    :param message: Explanation of the error.
    """
    def __init__(self, message: str | None = None, field: Any | None = None):
        super().__init__(value=field, message=message)
