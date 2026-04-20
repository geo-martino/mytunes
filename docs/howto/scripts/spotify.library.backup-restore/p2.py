from typing import Any

from p1 import *

import asyncio

from mytunes.libraries.remote._core.library import RemoteLibrary

with open(path, "r") as file:
    backup = json.load(file)


async def restore_remote_library(library: RemoteLibrary, backup: dict[str, Any]) -> None:
    """Restore the playlists in a remote ``library`` from the given ``backup``"""
    async with library:
        await library.restore_playlists(backup["playlists"])
        results = await library.sync(kind="refresh", reload=False, dry_run=False)

    library.log_sync(results)

asyncio.run(restore_remote_library(library, backup))
