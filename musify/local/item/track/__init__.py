from pydantic import TypeAdapter

from ._base import LocalTrack, HasLocalTracks, TagContext

__all__ = [
    LocalTrack.__name__,
    TagContext.__name__,
]

# we must import all the supported formats here so that they are registered in the registry
from .flac import FLAC
from .m4a import M4A
from .mp3 import MP3
from .wma import WMA

LOCAL_TRACK_ADAPTER = TypeAdapter[LocalTrack](LocalTrack.annotation)
