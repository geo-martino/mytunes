import asyncio

from mytunes.libraries.local.track import FLAC, MP3, M4A, WMA

track = FLAC("<PATH TO A FLAC TRACK>")
asyncio.run(track.load())

track = MP3("<PATH TO AN MP3 TRACK>")
asyncio.run(track.load())

track = M4A("<PATH TO AN M4A TRACK>")
asyncio.run(track.load())

track = WMA("<PATH TO A WMA TRACK>")
asyncio.run(track.load())

# pretty print information about this track
print(track)
