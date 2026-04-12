from mytunes.libraries.local.library import LocalLibrary
from mytunes.libraries.remote.spotify.api import SpotifyAPI
from mytunes.libraries.remote.spotify.library import SpotifyLibrary

local_library = LocalLibrary()

api = SpotifyAPI()
remote_library = SpotifyLibrary(api=api)
