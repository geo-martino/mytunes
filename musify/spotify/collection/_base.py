from typing import final

from musify.models.collection import PageCursor, RemoteCollection
from musify.spotify import SpotifyModel, SpotifyResource


@final
class SpotifyPageCursor(PageCursor, SpotifyModel):
    __final__ = True


# noinspection PyAbstractClass
class SpotifyCollection[IT: SpotifyResource](SpotifyModel, RemoteCollection[IT, SpotifyPageCursor]):
    pass
