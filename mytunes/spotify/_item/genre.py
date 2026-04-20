from typing import final

from mytunes.spotify import SpotifyModel
from mytunes.core.genre import RemoteGenre


@final
class SpotifyGenre(RemoteGenre[None], SpotifyModel):
    __final__ = True

    uri: None = None
