from abc import ABCMeta

from musify.remote.collection import RemoteCollection
from musify.remote.collection._base import ItemsCursor


class SpotifyCollection(RemoteCollection, metaclass=ABCMeta):
    pass


class SpotifyItemsCursor(ItemsCursor):
    pass
