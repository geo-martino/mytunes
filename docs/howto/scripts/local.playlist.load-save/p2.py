from p1 import *

from mytunes.libraries.local.playlist import XAutoPF

playlist = M3U("<PATH TO AN M3U PLAYLIST>")
asyncio.run(playlist.load())

# for some playlist types, you will need to provide
# a list of tracks to choose from in order to load them
playlist = XAutoPF("<PATH TO AN XAUTOPF PLAYLIST>")
asyncio.run(playlist.load(tracks=tracks))
