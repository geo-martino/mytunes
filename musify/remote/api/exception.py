from musify.exception import MusifyError


class RemoteError(MusifyError):
    """Exception raised for remote errors"""


class APIError(RemoteError):
    """Exception raised for REST API errors"""

