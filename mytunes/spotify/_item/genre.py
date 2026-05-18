from typing import final

from mytunes.core.genre import RemoteGenre
from mytunes.spotify import SpotifyModel


@final
class SpotifyGenre(RemoteGenre[None], SpotifyModel):
    __final__ = True

    uri: None = None
