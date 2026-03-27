from p1 import *

playlist = library.playlists["<NAME OF YOUR PLAYLIST>"]  # case sensitive
album = next(album for album in library.albums if album.name == "<ALBUM NAME>")
artist = next(artist for artist in library.artists if artist.name == "<ARTIST NAME>")
folder = next(folder for folder in library.folders if folder.name == "<FOLDER NAME>")
genre = next(genre for genre in library.genres if genre.name == "<GENRE NAME>")

# pretty print information about the loaded objects
print(playlist, album, artist, folder, genre, sep="\n")
