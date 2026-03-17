from typing import final

from musify.local._base import LocalModel
from musify.local.item.genre import LocalGenre
from musify.models.item.artist import Artist
from musify.models.properties.uri import URI


@final
class LocalArtist[GT: LocalGenre](Artist[GT, URI.annotation], LocalModel):
    __final__ = True
