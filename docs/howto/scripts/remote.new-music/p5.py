from p4 import *

from mytunes.libraries.remote.spotify.object import SpotifyPlaylist


async def create_new_music_playlist(name: str, library: RemoteLibrary, start: date, end: date) -> None:
    """
    Create a playlist with the given ``name`` in the given ``library`` featuring
    new music by followed artists released between ``start`` date and ``end`` date.
    """
    await load_artists(library)
    albums = await get_albums(library, start, end)

    # log stats about the loaded artists
    library.log_artists()

    async with library:
        playlist = await SpotifyPlaylist.create(api=api, name=name)

        tracks = [track for album in sorted(albums, key=lambda x: x.date, reverse=True) for track in album]
        playlist.extend(tracks, allow_duplicates=False)

        # sync the object with Spotify and log the results
        results = await playlist.sync(kind="refresh", reload=False, dry_run=False)
        library.log_sync({name: results})
