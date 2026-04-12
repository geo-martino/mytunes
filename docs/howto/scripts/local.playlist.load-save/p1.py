import asyncio

from mytunes.libraries.local.playlist import M3U
from mytunes.libraries.local.track import load_track

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

track_tasks = asyncio.gather(
    load_track("<PATH TO A TRACK>"),
    load_track("<PATH TO A TRACK>"),
    load_track("<PATH TO A TRACK>"),
    load_track("<PATH TO A TRACK>"),
)
tracks = loop.run_until_complete(track_tasks)
loop.close()

playlist = M3U("<PATH TO AN M3U PLAYLIST>")
playlist.extend(tracks)

# pretty print information about this playlist
print(playlist)
