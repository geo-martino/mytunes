from musify.local._base import LocalResource
from musify.local.item.genre import LocalGenre
from musify.model.item.artist import Artist


class LocalArtist[GT: LocalGenre](LocalResource, Artist[GT]):
    pass
