from typing import final

from musify.remote.item.genre import RemoteGenre
from musify.spotify import SpotifyModel


@final
class SpotifyGenre(RemoteGenre[None], SpotifyModel):
    __final__ = True

    uri: None = None
