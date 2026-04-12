from mytunes.libraries.remote.spotify.api import SpotifyAPI
from mytunes.libraries.remote.spotify.library import SpotifyLibrary

api = SpotifyAPI()
library = SpotifyLibrary(api=api)
