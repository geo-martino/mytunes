from p2 import *

from mytunes.libraries.local.library import LocalLibrary
from mytunes.libraries.remote.core.library import RemoteLibrary


async def sync_local_playlist_with_remote(name: str, local_library: LocalLibrary, remote_library: RemoteLibrary):
    """Sync ``local_library`` playlist with given ``name`` to its matching ``remote_library`` playlist."""
    async with api:
        await remote_library.load_playlists()

        local_playlist = local_library.playlists[name]
        remote_playlist = remote_library.playlists[name]

        # sync the object with Spotify and pretty print info about the reloaded remote playlist
        await remote_playlist.sync(items=local_playlist, kind="new", reload=True, dry_run=False)

    print(remote_playlist)
