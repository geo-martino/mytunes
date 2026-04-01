from pydantic import TypeAdapter

from ._base import LocalPlaylistFile, LocalPlaylist


__all__ = [
    LocalPlaylist.__name__,
    LocalPlaylistFile.__name__,
]

# we must import all the supported formats here so that they are registered in the registry
from .m3u import M3U
from .xautopf import XAutoPF

LOCAL_PLAYLIST_ADAPTER = TypeAdapter[LocalPlaylist](LocalPlaylist.annotation)
