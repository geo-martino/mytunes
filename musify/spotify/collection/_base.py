from typing import final

from musify.remote.collection import RemoteCollection, ItemsCursor
from musify.spotify import SpotifyModel, SpotifyResource


# noinspection PyAbstractClass
class SpotifyCollection[IT: SpotifyResource](RemoteCollection[IT], SpotifyModel):
    pass


@final
class SpotifyItemsCursor(ItemsCursor, SpotifyModel):
    __final__ = True
