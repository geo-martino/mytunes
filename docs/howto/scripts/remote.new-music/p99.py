from p5 import *

import asyncio
from datetime import datetime, timedelta

from mytunes.libraries.remote.spotify.library import SpotifyLibrary

playlist_name = "New Music Playlist"
library = SpotifyLibrary(api=api)
end = datetime.now().date()
start = end - timedelta(weeks=4)

asyncio.run(create_new_music_playlist(playlist_name, library, start, end))
