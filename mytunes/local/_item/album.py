from typing import final

from mytunes.core.album import Album
from mytunes.local._base import LocalModel
from mytunes.local._item.artist import LocalArtist
from mytunes.local._item.genre import LocalGenre


@final
class LocalAlbum[RT: LocalArtist, GT: LocalGenre](Album[RT, GT], LocalModel):
    __final__ = True
