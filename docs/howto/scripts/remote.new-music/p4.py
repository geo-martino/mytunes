from p3 import *

from musify.libraries.remote.core.types import RemoteObjectType
from musify.libraries.remote.core.object import RemoteAlbum


async def get_albums(library: RemoteLibrary, start: date, end: date) -> list[RemoteAlbum]:
    """
    Get the albums that match the ``start`` and ``end`` date range from a given ``library``
    and get the tracks on those albums if needed.
    """
    albums = [album for artist in library.artists for album in artist.albums if match_date(album, start, end)]
    albums_need_extend = [album for album in albums if len(album.tracks) < album.track_total]

    if not albums_need_extend:
        return albums

    kind = RemoteObjectType.ALBUM
    key = api.collection_item_map[kind]

    async with library:
        await library.logger.get_asynchronous_iterator(
            (api.extend_items(album.response, kind=kind, key=key) for album in albums),
            desc="Getting album tracks",
            unit="albums"
        )

    for album in albums:
        album.refresh(skip_checks=False)

    return albums
