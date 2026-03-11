from typing import ClassVar

from musify.models.remote import RemoteModel, RemoteResource
# noinspection PyProtectedMember
from musify.spotify.properties.uri import _SpotifyURIBase


class SpotifyModel(RemoteModel):
    source: ClassVar[str] = "spotify"


class SpotifyResource[UT: _SpotifyURIBase](RemoteResource[UT], SpotifyModel):
    pass
