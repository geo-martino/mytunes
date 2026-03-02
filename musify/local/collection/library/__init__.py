from ._base import LocalLibrary

__all__ = [LocalLibrary.__name__]

# we must import all the supported formats here so that they are registered in the registry
from .musicbee import MusicBee
