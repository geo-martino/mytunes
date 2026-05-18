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


class MyTunesValidationError(MyTunesValueError):
    """Exception raised for invalid values when validating models."""


class ModelError(MyTunesTypeError):
    """Exception raised for invalid model definitions or structures."""


class RemoteError(MyTunesError):
    """Exception raised for remote errors"""


class APIError(RemoteError):
    """Exception raised for API errors"""


class AuthenticationError(APIError):
    """Exception raised when trying to authenticate with the API server"""


class EndpointsError(APIError):
    """Exception raised for availability of API endpoints on an API model"""


class CursorError(APIError):
    """Exception raised for cursor errors during API operations"""


class RequestError(APIError):
    """Exception raised for API request errors"""


class ResponseError(APIError):
    """Exception raised for API response errors"""


class APIModelError(ResponseError):
    """Exception raised for API errors relating to the creation of models from responses"""


class CursorResponseError(ResponseError, CursorError):
    """Exception raised for API errors relating to the creation of models from responses"""
