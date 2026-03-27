# Musify

[![PyPI Version](https://img.shields.io/pypi/v/musify?logo=pypi&label=Latest%20Version)](https://pypi.org/project/musify)
[![Python Version](https://img.shields.io/pypi/pyversions/musify.svg?logo=python&label=Supported%20Python%20Versions)](https://pypi.org/project/musify/)
[![Documentation](https://img.shields.io/badge/Documentation-red.svg)](https://geo-martino.github.io/musify/)
</br>
[![PyPI Downloads](https://img.shields.io/pypi/dm/musify?label=Downloads)](https://pypi.org/project/musify/)
[![Code Size](https://img.shields.io/github/languages/code-size/geo-martino/musify?label=Code%20Size)](https://github.com/geo-martino/musify)
[![Contributors](https://img.shields.io/github/contributors/geo-martino/musify?logo=github&label=Contributors)](https://github.com/geo-martino/musify/graphs/contributors)
[![License](https://img.shields.io/github/license/geo-martino/musify?label=License)](https://github.com/geo-martino/musify/blob/master/LICENSE)
</br>
[![GitHub - Validate](https://github.com/geo-martino/musify/actions/workflows/validate.yml/badge.svg?branch=master)](https://github.com/geo-martino/musify/actions/workflows/validate.yml)
[![GitHub - Deployment](https://github.com/geo-martino/musify/actions/workflows/deploy.yml/badge.svg?event=release)](https://github.com/geo-martino/musify/actions/workflows/deploy.yml)
[![GitHub - Documentation](https://github.com/geo-martino/musify/actions/workflows/docs_publish.yml/badge.svg)](https://github.com/geo-martino/musify/actions/workflows/docs_publish.yml)

### A Swiss Army knife for music library management
Supporting local and music streaming service (remote) libraries.
- Extract data for all item types from remote libraries, including following/saved items, such as:
**playlists, tracks, albums, artists, users, podcasts, audiobooks**
- Load local audio files, programmatically manipulate, and save tags/metadata/embedded images
- Synchronise local tracks metadata with its matching track's metadata on supported music streaming services
- Synchronise local playlists with playlists on supported music streaming services
- Backup and restore track tags/metadata and playlists for local and remote libraries
- Extract and save images from remote tracks or embedded in local tracks

## Contents

* [Quick Guides](#quick-guides)
  * [Spotify](#spotify)
  * [Local](#local)
* [Currently Supported](#currently-supported)
* [Motivation and Aims](#motivation-and-aims)
* [Release History](#release-history)
* [Contributing and Reporting Issues](#contributing-and-reporting-issues)
* [Author Notes](#author-notes)

> [!NOTE]  
> This readme provides a brief overview of the program. 
> [Read the docs](https://geo-martino.github.io/musify/) for full reference documentation.


## Installation
Install through pip using one of the following commands:

```bash
pip install musify
```
```bash
python -m pip install musify
```

There are optional dependencies that you may install for optional functionality. 
For the current list of optional dependency groups, [read the docs](https://geo-martino.github.io/musify/howto/install.html)


## Quick Guides

These quick guides will help you get set up and going with Musify in just a few minutes.
For more detailed guides, check out the [documentation](https://geo-martino.github.io/musify/).

> [!TIP]
> Set up logging to ensure you can see all info reported by the later operations.
> Libraries log info about loaded objects to the custom `STAT` level.
> ```python
> import logging
> import sys
> from musify.logger import STAT
> 
> logging.basicConfig(format="%(message)s", level=STAT, stream=sys.stdout)
> ```

### Spotify

> In this example, you will: 
> - Authorise access to the [Spotify Web API](https://developer.spotify.com/documentation/web-api)
> - Load your Spotify library
> - Load some other Spotify objects
> - Add some tracks to a playlist

1. If you don't already have one, create a [Spotify for Developers](https://developer.spotify.com/dashboard) account. 
2. If you don't already have one, [create an app](https://developer.spotify.com/documentation/web-api/concepts/apps). 
   Select "Web API" when asked which APIs you are planning on using. 
   To use this program, you will only need to take note of the **client ID** and **client secret**.
3. Create a `SpotifyAPI` object and authorise the program access to Spotify data as follows:
   
   > The scopes listed in this example will allow access to read your library data and write to your playlists.
   > See Spotify Web API documentation for more information about [scopes](https://developer.spotify.com/documentation/web-api/concepts/scopes)
   ```python
    from musify.libraries.remote.spotify.api import SpotifyAPI
   
    spotify_api = SpotifyAPI(
        client_id="<YOUR CLIENT ID>",
        client_secret="<YOUR CLIENT SECRET>",
        scope=[
            "user-library-read",
            "user-follow-read",
            "playlist-read-collaborative",
            "playlist-read-private",
            "playlist-modify-public",
            "playlist-modify-private"
        ],
        # providing a `token_file_path` will save the generated token to your system 
        # for quicker authorisations in future
        token_file_path="<PATH TO JSON TOKEN>"  
    )
   ```
4. Define helper functions for loading your `SpotifyLibrary` data:
   ```python
    from musify.libraries.remote.spotify.library import SpotifyLibrary


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
   ```
5. Define helper functions for loading some Spotify objects using any of the supported identifiers:
   ```python
    from musify.libraries.remote.spotify.object import SpotifyTrack, SpotifyAlbum, SpotifyPlaylist, SpotifyArtist


    async def load_playlist(api: SpotifyAPI) -> SpotifyPlaylist:
        # authorise the program to access your Spotify data in your web browser
        async with api as a:
            playlist = await SpotifyPlaylist.load("spotify:playlist:37i9dQZF1E4zg1xOOORiP1", api=a, extend_tracks=True)
        return playlist


    async def load_tracks(api: SpotifyAPI) -> list[SpotifyTrack]:
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
        # authorise the program to access your Spotify data in your web browser
        async with api as a:
            album = await SpotifyAlbum.load(
                "https://open.spotify.com/album/0rAWaAAMfzHzCbYESj4mfx", api=a, extend_tracks=True
            )
        return album


    async def load_artist(api: SpotifyAPI) -> SpotifyArtist:
        # authorise the program to access your Spotify data in your web browser
        async with api as a:
            artist = await SpotifyArtist.load("1odSzdzUpm3ZEEb74GdyiS", api=a, extend_tracks=True)
        return artist


    async def load_objects(api: SpotifyAPI) -> None:
        playlist = await load_playlist(api)
        tracks = await load_tracks(api)
        album = await load_album(api)
        artist = await load_artist(api)

        # pretty print information about the loaded objects
        print(playlist, *tracks, album, artist, sep="\n")
   ```
6. Define helper function for adding some tracks to a playlist in your library, synchronising with Spotify, and logging the results:
   
   > **NOTE**: This step will only work if you chose to load either your playlists or your entire library in step 4.
   ```python   
    async def update_playlist(name: str, library: SpotifyLibrary) -> None:
        """Update a playlist with the given ``name`` in the given ``library``"""
        tracks = await load_tracks(library.api)
        album = await load_album(library.api)
        await load_library(library)

        my_playlist = library.playlists[name]

        # add a track to the playlist
        my_playlist.append(tracks[0])

        # add an album to the playlist using either of the following
        my_playlist.extend(album)
        my_playlist += album

        # sync the object with Spotify and log the results
        async with library:
            result = await my_playlist.sync(dry_run=False)
        library.log_sync(result)
    
    asyncio.run(update_playlist(spotify_api))
   ```
7. Run the program:
   ```python
    import asyncio

    asyncio.run(load_objects(api))
    asyncio.run(update_playlist("<YOUR PLAYLIST'S NAME>", api))  # case sensitive
   ```

### Local

> In this example, you will: 
> - Load a local library
> - Modify the tags of some local tracks and save them
> - Modify a local playlist and save it

1. Create one of the following supported `LocalLibrary` objects:

   #### Generic local library
   ```python
   from musify.libraries.local.library import LocalLibrary
   
   library = LocalLibrary(
       library_folders=["<PATH TO YOUR LIBRARY FOLDER>", ...],
       playlist_folder="<PATH TO YOUR PLAYLIST FOLDER",
   )
   ```
   
   #### MusicBee
   > You will need to install the `musicbee` optional dependency to work with MusicBee objects.
   > [Read the docs](https://geo-martino.github.io/musify/howto.install.html) for more info.
   ```python
   from musify.libraries.local.library import MusicBee
   
   library = MusicBee(musicbee_folder="<PATH TO YOUR MUSICBEE FOLDER>")
   ```

2. Load your library:
   ```python
   # if you have a very large library, this will take some time...
   library.load()
   
   # ...or you may also just load distinct sections of your library
   library.load_tracks()
   library.load_playlists()
   
   # optionally log stats about these sections
   library.log_tracks()
   library.log_playlists()
   
   # pretty print an overview of your library
   print(library)
   ```
   
3. Get collections from your library:
   ```python
   playlist = library.playlists["<NAME OF YOUR PLAYLIST>"]  # case sensitive
   album = next(album for album in library.albums if album.name == "<ALBUM NAME>")
   artist = next(artist for artist in library.artists if artist.name == "<ARTIST NAME>")
   folder = next(folder for folder in library.folders if folder.name == "<FOLDER NAME>")
   genre = next(genre for genre in library.genres if genre.name == "<GENRE NAME>")
   
   # pretty print information about the loaded objects
   print(playlist, album, artist, folder, genre, sep="\n")
   ```

4. Get a track from your library using any of the following identifiers:
   ```python
   # get a track via its title
   # if multiple tracks have the same title, the first matching one if returned
   track = library["<TRACK TITLE>"]
   
   # get a track via its path
   track = library["<PATH TO YOUR TRACK>"]  # must be an absolute path
   
   # get a track according to a specific tag
   track = next(track for track in library if track.artist == "<ARTIST NAME>")
   track = next(track for track in library if "<GENRE>" in (track.genres or []))
   
   # pretty print information about this track
   print(track)
   ```

5. Change some tags:
   ```python
   from datetime import date
   
   track.title = "new title"
   track.artist = "new artist"
   track.album = "new album"
   track.track_number = 200
   track.genres = ["super cool genre", "awesome genre"]
   track.key = "C#"
   track.bpm = 120.5
   track.date = date(year=2024, month=1, day=1)
   track.compilation = True
   track.image_links.update({
        "cover front": "https://i.scdn.co/image/ab67616d0000b2737f0918f1560fc4b40b967dd4",
        "cover back": "<PATH TO AN IMAGE ON YOUR LOCAL DRIVE>"
   })
   
   # see the updated information
   print(track)
   ```

6. Save the tags to the file:
   ```python
   from musify.libraries.local.track.field import LocalTrackField
   
   # you don't have to save all the tags you just modified
   # select which you wish to save first like so
   tags = [
        LocalTrackField.TITLE,
        LocalTrackField.GENRES,
        LocalTrackField.KEY,
        LocalTrackField.BPM,
        LocalTrackField.DATE,
        LocalTrackField.COMPILATION,
        LocalTrackField.IMAGES
   ]
   
   track.save(tags=tags, replace=True, dry_run=False)
   ```

7. Add some tracks to one of your playlists and save it:
   ```python
   my_playlist = library.playlists["<NAME OF YOUR PLAYLIST>"]  # case sensitive
   
   # add a track to the playlist
   my_playlist.append(track)
   
   # add album's and artist's tracks to the playlist using either of the following
   my_playlist.extend(album)
   my_playlist += artist
   
   result = my_playlist.save(dry_run=False)
   print(result)
   ```

## Currently Supported

- **Music Streaming Services**: `Spotify`
- **Audio filetypes**: `.flac` `.m4a` `.mp3` `.wma`
- **Local playlist filetypes**: `.m3u` `.xautopf`
- **Local Libraries**: `MusicBee`


## Motivation and Aims

The key aim of this package is to provide a seamless framework for interoperability between all types of music 
libraries whether local or remote. </br>

**This framework should allow for the following key functionality between libraries:**

- Synchronise saved user data including: 
  - playlists data (e.g. name, description, tracks)
  - saved tracks/albums/artists etc.
- Synchronise metadata by allowing users to pull metadata from music streaming services and save this to local tracks
- Provide tools to allow users to move from music streaming services to a local library by semi-automating the process 
of purchasing songs.

**With this functionality, user's should then have the freedom to**:

- Switch between music streaming services with a few simple commands
- Share local playlists and other local library data with friends over music streaming services 
without ever having to use them personally
- Easily maintain a high-quality local library with complete metadata

**Users should have the freedom to choose how and where they want to listen to their favourite artists.**

Given the near non-existence of income these services provide to artists, user's should have the choice to 
compensate their favourite artists fairly for their work, choosing to switch to other services that do and/or choosing 
not to use music streaming services altogether because of this. Hopefully, by reintroducing this choice to users, 
the music industry will be forced to re-evaluate their complete devaluing of creative work in the rush to chase profits, 
and instead return to a culture of nurturing talent by providing artists with a basic income to survive 
on the work of their craft. One can dream.


## Release History

For change and release history, 
check out the [documentation](https://geo-martino.github.io/musify/info/release-history.html).


## Contributing and Reporting Issues

If you have any suggestions, wish to contribute, or have any issues to report, please do let me know 
via the issues tab or make a new pull request with your new feature for review. 

For more info on how to contribute to Musify, 
check out the [documentation](https://geo-martino.github.io/musify/info/contributing.html).


## Author notes

I initially developed this program for my own use so that I can share my local playlists with friends online. 
I have always maintained my own local library well and never saw the need to switch to music 
streaming services after their release. However, as an artist who has released music on all streaming services 
and after listening to the concerns many of the artists I follow have regarding these services, I started to refocus 
this project to be one that aims to break down the barriers between listening experiences for users. 
The ultimate aim being to make managing a local library as easy as any of the major music streaming services, 
allowing users the same conveniences while compensating artists fairly for their work.

I hope you enjoy using Musify!
