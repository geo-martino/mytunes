from typing import ClassVar

from musify.models.remote import RemoteModel, RemoteResource
from ._properties.uri import SpotifyURIBase


class SpotifyModel(RemoteModel):
    source: ClassVar[str] = "spotify"


# noinspection PyAbstractClass
class SpotifyResource[UT: SpotifyURIBase](RemoteResource[UT], SpotifyModel):
    pass
