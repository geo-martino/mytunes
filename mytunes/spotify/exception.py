from mytunes.exception import RemoteError, APIError, AuthenticationError


class SpotifyError(RemoteError):
    """Exception raised for Spotify errors"""


class SpotifyAPIError(SpotifyError, APIError):
    """Exception raised for Spotify API errors"""


class SpotifyAuthenticationError(SpotifyAPIError, AuthenticationError):
    """Exception raised for Spotify API errors"""
