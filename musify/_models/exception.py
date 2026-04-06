from musify.exception import MusifyValueError, MusifyError, MusifyTypeError


class MusifyValidationError(MusifyValueError):
    """Exception raised for invalid values when validating models."""


class ModelError(MusifyTypeError):
    """Exception raised for invalid model definitions or structures."""


class RemoteError(MusifyError):
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
