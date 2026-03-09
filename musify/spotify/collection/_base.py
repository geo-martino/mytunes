from typing import final

from musify.remote.collection import RemoteCollection, ItemsCursor
from musify.spotify import SpotifyModel, SpotifyResource


@final
class SpotifyItemsCursor(ItemsCursor, SpotifyModel):
    __final__ = True


# noinspection PyAbstractClass
class SpotifyCollection[IT: SpotifyResource](SpotifyModel, RemoteCollection[IT, SpotifyItemsCursor]):
    pass
