"""
Utilities for operations on :py:class:`LocalPlaylist` types.

Generally, this will contain global variables representing all supported playlist file types
and a utility function for loading the appropriate :py:class:`LocalPlaylist` type for a path based on its extension.
"""
from collections.abc import Collection
from pathlib import Path

from musify.file.exception import InvalidFileType
from musify.file.path_mapper import PathMapper
from musify.libraries.local.playlist.base import LocalPlaylist
from musify.libraries.local.playlist.m3u import M3U
from musify.libraries.local.playlist.xautopf import XAutoPF, REQUIRED_MODULES as REQUIRED_XAUTOPF_MODULES
from musify.libraries.local.track import LocalTrack
from musify.libraries.remote.core.wrangle import RemoteDataWrangler
from musify.utils import required_modules_installed

_playlist_classes = {M3U}
if required_modules_installed(REQUIRED_XAUTOPF_MODULES):
    _playlist_classes.add(XAutoPF)

PLAYLIST_CLASSES = frozenset(_playlist_classes)
PLAYLIST_FILETYPES = frozenset(filetype for c in PLAYLIST_CLASSES for filetype in c.valid_extensions)


async def load_playlist(
        path: str | Path,
        tracks: Collection[LocalTrack] = (),
        path_mapper: PathMapper = PathMapper(),
        remote_wrangler: RemoteDataWrangler = None,
) -> LocalPlaylist:
    """
    Attempt to load a file from a given path, returning the appropriate :py:class:`LocalPlaylist` object

    :param path: Absolute path of the playlist.
        If the playlist ``path`` given does not exist, the playlist instance will use all the tracks
        given in ``tracks`` as the tracks in the playlist.
    :param tracks: Optional. Available Tracks to search through for matches.
        If no tracks are given, the playlist instance will load all the tracks from scratch according to its settings.
    :param path_mapper: Optionally, provide a :py:class:`PathMapper` for paths stored in the playlist file.
        Useful if the playlist file contains relative paths and/or paths for other systems that need to be
        mapped to absolute, system-specific paths to be loaded and back again when saved.
    :param remote_wrangler: Optionally, provide a :py:class:`RemoteDataWrangler` object for processing URIs on tracks.
        If given, the wrangler can be used when calling __get_item__ to get an item from the collection from its URI.
        The wrangler is also used when loading tracks to allow them to process URI tags.
        For more info on this, see :py:class:`LocalTrack`.
    :return: Loaded :py:class:`LocalPlaylist` object
    :raise InvalidFileType: If the file type is not supported.
    """
    ext = Path(path).suffix
    if ext not in PLAYLIST_FILETYPES:
        raise InvalidFileType(ext, f"Not an accepted extension. Use only: {', '.join(PLAYLIST_FILETYPES)}")

    cls = next(cls for cls in PLAYLIST_CLASSES if ext in cls.valid_extensions)
    playlist = cls(path=path, path_mapper=path_mapper, remote_wrangler=remote_wrangler)
    return await playlist.load(tracks=tracks)
