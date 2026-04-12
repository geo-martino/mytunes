from p0 import *

from collections.abc import Collection

from mytunes.libraries.core.collection import MyTunesCollection
from mytunes.libraries.remote.core.factory import RemoteObjectFactory
from mytunes.processors.search import RemoteItemSearcher
from mytunes.processors.check import RemoteItemChecker
from mytunes.processors.match import ItemMatcher


async def match_albums_to_remote(albums: Collection[MyTunesCollection], factory: RemoteObjectFactory) -> None:
    """Match the items in the given ``albums`` to the remote API's database and assign URIs to them."""
    matcher = ItemMatcher()

    searcher = RemoteItemSearcher(matcher=matcher, object_factory=factory)
    async with searcher:
        await searcher(albums)

    checker = RemoteItemChecker(matcher=matcher, object_factory=factory)
    async with checker:
        await checker(albums)
