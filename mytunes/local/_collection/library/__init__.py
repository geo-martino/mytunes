from ._base import LocalLibrary
from ._path import LocalSystemPath, LocalSystemPaths

__all__ = [
    LocalLibrary.__name__,
    LocalSystemPath.__name__,
    LocalSystemPaths.__name__,
]

# we must import all the supported formats here so that they are registered in the registry
from .musicbee import MusicBee
