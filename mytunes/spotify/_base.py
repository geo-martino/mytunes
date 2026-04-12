from typing import ClassVar

from ._properties.uri import SpotifyURIBase
from .._models.remote import RemoteModel, RemoteResource


class SpotifyModel(RemoteModel):
    source: ClassVar[str] = "spotify"


# noinspection PyAbstractClass
class SpotifyResource[UT: SpotifyURIBase](RemoteResource[UT], SpotifyModel):
    pass
