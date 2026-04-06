from typing import final

from musify.spotify import SpotifyModel
from ..._models.item.genre import RemoteGenre


# TODO: consider dropping this?  No such thing as Genre URI so typing gets a bit funky
@final
class SpotifyGenre(RemoteGenre[None], SpotifyModel):
    __final__ = True

    uri: None = None
