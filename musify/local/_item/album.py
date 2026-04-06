from typing import final

from musify.local._base import LocalModel
from musify.local._item.artist import LocalArtist
from musify.local._item.genre import LocalGenre
from musify.models.item.album import Album


@final
class LocalAlbum[RT: LocalArtist, GT: LocalGenre](Album[RT, GT], LocalModel):
    __final__ = True
