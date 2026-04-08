from typing import final

from musify.spotify import SpotifyModel
from ..._models.item.genre import RemoteGenre


@final
class SpotifyGenre(RemoteGenre[None], SpotifyModel):
    __final__ = True

    uri: None = None
