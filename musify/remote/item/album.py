from pydantic import Field, PositiveInt

from musify.models import readable_computed_field
from musify.models.item.album import Album
from musify.remote._base import RemoteResource
from musify.remote.item.artist import RemoteArtist
from musify.remote.item.genre import RemoteGenre


class RemoteAlbum[RT: RemoteArtist, GT: RemoteGenre](RemoteResource, Album[RT, GT]):
    track_total = readable_computed_field("track_total")
    disc_total = readable_computed_field("disc_total")
