from typing import final

from musify.models.collection import ItemsCursor, RemoteCollection
from musify.spotify import SpotifyModel, SpotifyResource


@final
class SpotifyItemsCursor(ItemsCursor, SpotifyModel):
    __final__ = True


# noinspection PyAbstractClass
class SpotifyCollection[IT: SpotifyResource](SpotifyModel, RemoteCollection[IT, SpotifyItemsCursor]):
    pass
