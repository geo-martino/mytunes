from typing import ClassVar

from ._properties.uri import SpotifyURIBase
from ._url import SOURCE_NAME
from ..core.remote import RemoteModel, RemoteResource


class SpotifyModel(RemoteModel):
    source: ClassVar[str] = SOURCE_NAME


# noinspection PyAbstractClass
class SpotifyResource[UT: SpotifyURIBase](RemoteResource[UT], SpotifyModel):
    pass
