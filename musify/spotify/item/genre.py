from typing import final

from musify.remote.item.genre import RemoteGenre


@final
class SpotifyGenre(RemoteGenre[None]):
    __final__ = True
