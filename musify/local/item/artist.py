from typing import final

from musify.local._base import LocalResource
from musify.local.item.genre import LocalGenre
from musify.models.item.artist import Artist
from musify.models.properties.uri import URI


@final
class LocalArtist[GT: LocalGenre](Artist[GT, URI], LocalResource):
    __final__ = True
