from abc import ABCMeta

from musify.remote.collection import RemoteCollection, ItemsCursor


class SpotifyCollection(RemoteCollection, metaclass=ABCMeta):
    pass


class SpotifyItemsCursor(ItemsCursor):
    pass
