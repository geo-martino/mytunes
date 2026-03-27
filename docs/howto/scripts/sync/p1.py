from p0 import *

from collections.abc import Collection

from musify.libraries.core.collection import MusifyCollection
from musify.libraries.remote.core.factory import RemoteObjectFactory
from musify.processors.search import RemoteItemSearcher
from musify.processors.check import RemoteItemChecker
from musify.processors.match import ItemMatcher


async def match_albums_to_remote(albums: Collection[MusifyCollection], factory: RemoteObjectFactory) -> None:
    """Match the items in the given ``albums`` to the remote API's database and assign URIs to them."""
    matcher = ItemMatcher()

    searcher = RemoteItemSearcher(matcher=matcher, object_factory=factory)
    async with searcher:
        await searcher(albums)

    checker = RemoteItemChecker(matcher=matcher, object_factory=factory)
    async with checker:
        await checker(albums)
