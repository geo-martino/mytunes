from typing import final

from musify.local._base import LocalModel
from musify.local.item.artist import LocalArtist
from musify.local.item.genre import LocalGenre
from musify.models.item.album import Album
from musify.models.properties.uri import URI


@final
class LocalAlbum[RT: LocalArtist, GT: LocalGenre](Album[RT, GT, URI], LocalModel):
    __final__ = True
