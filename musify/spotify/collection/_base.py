from musify.models.collection import RemoteCollection
from musify.spotify import SpotifyModel, SpotifyResource
from musify.spotify.cursors import SpotifyPageCursor


# noinspection PyAbstractClass
class SpotifyCollection[IT: SpotifyResource](SpotifyModel, RemoteCollection[IT, SpotifyPageCursor]):
    pass
