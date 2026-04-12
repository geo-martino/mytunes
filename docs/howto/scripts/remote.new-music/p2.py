from p0 import *

from mytunes.libraries.remote.core.library import RemoteLibrary


async def load_artists(library: RemoteLibrary) -> None:
    """Loads the artists followed by a given user in their given ``library`` and enriches them."""
    async with library:
        await library.load_saved_artists()
        await library.enrich_saved_artists(types=("album", "single"))
