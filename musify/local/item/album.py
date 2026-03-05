from typing import final

from musify.local._base import LocalResource
from musify.local.item.artist import LocalArtist
from musify.local.item.genre import LocalGenre
from musify.models import writeable_computed_field
from musify.models.item.album import Album
from musify.models.properties.uri import URI


@final
class LocalAlbum[RT: LocalArtist, GT: LocalGenre](Album[RT, GT, URI], LocalResource):
    __final__ = True

    track_total = writeable_computed_field("track_total")
    disc_total = writeable_computed_field("disc_total")
