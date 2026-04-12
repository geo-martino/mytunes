from p0 import *

from mytunes.libraries.remote.spotify.object import SpotifyTrack, SpotifyAlbum, SpotifyPlaylist, SpotifyArtist


async def load_playlist(api: SpotifyAPI) -> SpotifyPlaylist:
    """Loads a playlist from the given ``api`` object"""
    # authorise the program to access your Spotify data in your web browser
    async with api as a:
        playlist = await SpotifyPlaylist.load("spotify:playlist:37i9dQZF1E4zg1xOOORiP1", api=a, extend_tracks=True)
    return playlist


async def load_tracks(api: SpotifyAPI) -> list[SpotifyTrack]:
    """Loads some tracks from the given ``api`` object"""
    tracks = []

    # authorise the program to access your Spotify data in your web browser
    async with api as a:
        # load by ID
        tracks.append(await SpotifyTrack.load("6fWoFduMpBem73DMLCOh1Z", api=a))
        # load by URI
        tracks.append(await SpotifyTrack.load("spotify:track:4npv0xZO9fVLBmDS2XP9Bw", api=a))
        # load by open/external style URL
        tracks.append(await SpotifyTrack.load("https://open.spotify.com/track/1TjVbzJUAuOvas1bL00TiH", api=a))
        # load by API style URI
        tracks.append(await SpotifyTrack.load("https://api.spotify.com/v1/tracks/6pmSweeisgfxxsiLINILdJ", api=api))

    return tracks


async def load_album(api: SpotifyAPI) -> SpotifyAlbum:
    """Loads an album from the given ``api`` object"""
    # authorise the program to access your Spotify data in your web browser
    async with api as a:
        album = await SpotifyAlbum.load(
            "https://open.spotify.com/album/0rAWaAAMfzHzCbYESj4mfx", api=a, extend_tracks=True
        )
    return album


async def load_artist(api: SpotifyAPI) -> SpotifyArtist:
    """Loads an artist from the given ``api`` object"""
    # authorise the program to access your Spotify data in your web browser
    async with api as a:
        artist = await SpotifyArtist.load("1odSzdzUpm3ZEEb74GdyiS", api=a, extend_tracks=True)
    return artist


async def load_objects(api: SpotifyAPI) -> None:
    """Loads multiple types of objects from the given ``api`` object and prints them"""
    playlist = await load_playlist(api)
    tracks = await load_tracks(api)
    album = await load_album(api)
    artist = await load_artist(api)

    # pretty print information about the loaded objects
    print(playlist, *tracks, album, artist, sep="\n")
