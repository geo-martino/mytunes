"""
Exceptions relating to local operations.
"""
from musify.exception import MusifyError


class LocalError(MusifyError):
    """
    Exception raised for local errors.

    :param message: Explanation of the error.
    """
    def __init__(self, message: str | None = None):
        self.message = message
        super().__init__(message)


class LocalItemError(LocalError):
    """
    Exception raised for local item errors.

    :param message: Explanation of the error.
    :param kind: The item type related to the error.
    """
    def __init__(self, message: str | None = None, kind: str | None = None):
        self.message = message
        self.kind = kind
        formatted = f"{kind} | {message}" if kind else message
        super().__init__(formatted)


class LocalCollectionError(LocalError):
    """
    Exception raised for local collection errors.

    :param message: Explanation of the error.
    :param kind: The collection type related to the error.
    """
    def __init__(self, message: str | None = None, kind: str | None = None):
        self.message = message
        self.kind = kind
        formatted = f"{kind} | {message}" if kind else message
        super().__init__(formatted)


###########################################################################
## Track errors
###########################################################################
class TagError(LocalError):
    """Exception raised for errors related to track tag errors."""


###########################################################################
## Library errors
###########################################################################
class LocalLibraryError(LocalError):
    """Exception raised for errors related to :py:class:`LocalLibrary` logic."""


class MusicBeeError(LocalLibraryError):
    """Exception raised for errors related to :py:class:`MusicBee` logic."""


class MusicBeeIDError(MusicBeeError):
    """Exception raised for errors related to MusicBee IDs."""


class XMLReaderError(MusicBeeError):
    """Exception raised for errors related to reading a MusicBee library XML file."""
