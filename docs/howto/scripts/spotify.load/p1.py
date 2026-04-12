from p2 import *

from mytunes.libraries.remote.spotify.library import SpotifyLibrary


async def load_library(library: SpotifyLibrary) -> None:
    """Load the objects for a given ``library``. Does not enrich the loaded data."""
    # authorise the program to access your Spotify data in your web browser
    async with library:
        # if you have a very large library, this will take some time...
        await library.load()


async def load_library_by_parts(library: SpotifyLibrary) -> None:
    """Load the objects for a given ``library`` by each of its distinct parts.  Does not enrich the loaded data."""
    # authorise the program to access your Spotify data in your web browser
    async with library:
        # load distinct sections of your library
        await library.load_playlists()
        await library.load_tracks()
        await library.load_saved_albums()
        await library.load_saved_artists()


async def enrich_library(library: SpotifyLibrary) -> None:
    """Enrich the loaded objects in the given ``library``"""
    # authorise the program to access your Spotify data in your web browser
    async with library:
        # enrich the loaded objects; see each function's docstring for more info on arguments
        # each of these will take some time depending on the size of your library
        await library.enrich_tracks(features=True, analysis=False, albums=False, artists=False)
        await library.enrich_saved_albums()
        await library.enrich_saved_artists(tracks=True, types=("album", "single"))


def log_library(library: SpotifyLibrary) -> None:
    """Log stats about the loaded ``library``"""
    library.log_playlists()
    library.log_tracks()
    library.log_albums()
    library.log_artists()

    # pretty print an overview of your library
    print(library)
