from musify.local._base import LocalResource
from musify.local.item.artist import LocalArtist
from musify.local.item.genre import LocalGenre
from musify.models import writeable_computed_field
from musify.models.item.album import Album


class LocalAlbum[RT: LocalArtist, GT: LocalGenre](LocalResource, Album[RT, GT]):
    track_total = writeable_computed_field("track_total")
    disc_total = writeable_computed_field("disc_total")
