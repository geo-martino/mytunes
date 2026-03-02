from ._base import LocalTrack, TagDumpContext

__all__ = [
    LocalTrack.__name__,
    TagDumpContext.__name__,
]

# we must import all the supported formats here so that they are registered in the registry
from .flac import FLAC
from .m4a import M4A
from .mp3 import MP3
from .wma import WMA
