from musify.models.exception import APIError, AuthenticationError, RemoteError


class SpotifyError(RemoteError):
    """Exception raised for Spotify errors"""


class SpotifyAPIError(SpotifyError, APIError):
    """Exception raised for Spotify API errors"""


class SpotifyAuthenticationError(SpotifyAPIError, AuthenticationError):
    """Exception raised for Spotify API errors"""
