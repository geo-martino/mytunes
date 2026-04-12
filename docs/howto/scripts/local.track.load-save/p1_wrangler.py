from p1_load import *

from mytunes.libraries.remote.spotify.wrangle import SpotifyDataWrangler

track = asyncio.run(load_track("<PATH TO A TRACK>", remote_wrangler=SpotifyDataWrangler()))
