"""
Utilities for operations on :py:class:`LocalTrack` types.

Generally, this will contain global variables representing all supported audio file types
and a utility function for loading the appropriate :py:class:`LocalTrack` type for a path based on its extension.
"""
from pathlib import Path

from musify.file.exception import InvalidFileType
from musify.libraries.local.track import LocalTrack
from musify.libraries.local.track.flac import FLAC
from musify.libraries.local.track.m4a import M4A
from musify.libraries.local.track.mp3 import MP3
from musify.libraries.local.track.wma import WMA
from musify.libraries.remote.core.wrangle import RemoteDataWrangler

TRACK_CLASSES = frozenset({FLAC, MP3, M4A, WMA})
TRACK_FILETYPES = frozenset(filetype for c in TRACK_CLASSES for filetype in c.valid_extensions)


async def load_track(path: str | Path, remote_wrangler: RemoteDataWrangler = None) -> LocalTrack:
    """
    Attempt to load a file from a given path, returning the appropriate :py:class:`LocalTrack` object

    :param path: The path of the file to load.
    :param remote_wrangler: Optionally, provide a :py:class:`RemoteDataWrangler` object for processing URIs.
        This object will be used to check for and validate a URI tag on the file.
        The tag that is used for reading and writing is set by the ``uri_tag`` class attribute on the track object.
        If no ``remote_wrangler`` is given, no URI processing will occur.
    :return: Loaded :py:class:`LocalTrack` object
    :raise InvalidFileType: If the file type is not supported.
    """
    ext = Path(path).suffix
    if ext not in TRACK_FILETYPES:
        raise InvalidFileType(ext, f"Not an accepted extension. Use only: {', '.join(TRACK_FILETYPES)}")

    cls = next(cls for cls in TRACK_CLASSES if ext in cls.valid_extensions)
    return await cls(file=path, remote_wrangler=remote_wrangler)
