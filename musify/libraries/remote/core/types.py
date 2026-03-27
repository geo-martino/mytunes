"""
All type hints to use throughout the module.
"""
from collections.abc import Mapping, MutableMapping
from typing import Any

from aiorequestful.types import UnitMutableSequence, UnitSequence, URLInput
from yarl import URL

from musify.libraries.remote.core import RemoteResponse
from musify.types import MusifyEnum

type APIInputValueSingle[T: RemoteResponse] = URLInput | Mapping[str, Any] | T
type APIInputValueMulti[T: RemoteResponse] = (
        UnitSequence[str] |
        UnitMutableSequence[URL] |
        UnitMutableSequence[MutableMapping[str, Any]] |
        UnitSequence[T]
)


class RemoteIDType(MusifyEnum):
    """Represents remote ID types"""
    ALL: int = 0

    #: Value is the expected length of ID string
    ID: int = 22
    #: Value is the expected number of chunks in a URI
    URI: int = 3
    URL: int = 1
    URL_EXT: int = 2


class RemoteObjectType(MusifyEnum):
    """Represents remote object types"""
    ALL = 0
    PLAYLIST = 1
    TRACK = 2
    ALBUM = 3
    ARTIST = 4
    USER = 5
    SHOW = 6
    EPISODE = 7
    AUDIOBOOK = 8
    CHAPTER = 9
