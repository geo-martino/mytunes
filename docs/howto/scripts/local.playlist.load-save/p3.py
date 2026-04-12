from p2 import *

from mytunes.libraries.local.playlist import load_playlist

# providing tracks is optional
playlist = asyncio.run(load_playlist("<PATH TO A PLAYLIST>", tracks=tracks))
