"""
Core exceptions for the entire package.
"""
from typing import Any


class MyTunesError(Exception):
    """Generic base class for all MyTunes-related errors"""


class MyTunesKeyError(MyTunesError, KeyError):
    """Exception raised for invalid keys."""


class MyTunesValueError(MyTunesError, ValueError):
    """Exception raised for invalid values."""


class MyTunesTypeError(MyTunesError, TypeError):
    """Exception raised for invalid types."""
    def __init__(self, kind: Any, message: str = "Invalid item type given"):
        self.message = message
        super().__init__(f"{self.message}: {kind}")


class MyTunesAttributeError(MyTunesError, AttributeError):
    """Exception raised for invalid attributes."""


class MyTunesImportError(MyTunesError, ImportError):
    """Exception raised for import errors, usually from missing modules."""
