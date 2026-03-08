from typing import final

from musify.remote.collection import RemoteCollection, ItemsCursor
from musify.spotify import SpotifyModel


# noinspection PyAbstractClass
class SpotifyCollection(RemoteCollection, SpotifyModel):
    pass


@final
class SpotifyItemsCursor(ItemsCursor, SpotifyModel):
    __final__ = True
