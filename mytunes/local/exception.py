"""
Exceptions relating to local operations.
"""
from pathlib import Path

from mytunes.exception import MyTunesError


###########################################################################
## File errors
###########################################################################
class FileError(MyTunesError, OSError):
    """
    Exception raised for file-related errors.

    :param path: The path that caused the error.
    :param message: Explanation of the error.
    """
    def __init__(self, path: str | Path | None = None, message: str | None = None):
        self.path = Path(path) if path is not None else None
        self.message = message
        formatted = f"{path} | {message}" if path else message
        super().__init__(formatted)


class FileDoesNotExistError(FileError, FileNotFoundError):
    """
    Exception raised when a file cannot be found.

    :param path: The path that caused the error.
    :param message: Explanation of the error.
    """
    def __init__(self, path: str | Path, message: str = "File cannot be found"):
        self.message = message
        super().__init__(path=path, message=message)


class XMLReaderError(FileError):
    """Exception raised for errors related to reading an XML file."""
