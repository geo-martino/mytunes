from p1 import *

from mytunes.libraries.local.collection import LocalAlbum


async def sync_albums(albums: list[LocalAlbum], factory: RemoteObjectFactory) -> None:
    """Sync the local ``albums`` with tag data from the api in the given ``factory``"""
    async with factory.api:
        for album in albums:
            for local_track in album:
                remote_track = await factory.track.load(local_track.uri, api=factory.api)

                local_track.title = remote_track.title
                local_track.artist = remote_track.artist
                local_track.date = remote_track.date
                local_track.genres = remote_track.genres
                local_track.image_links = remote_track.image_links

                # alternatively, just merge all tags
                local_track |= remote_track

                # save the track here or...
                await local_track.save(replace=True, dry_run=False)

            # ...save all tracks on the album at once here
            await album.save_tracks(replace=True, dry_run=False)
