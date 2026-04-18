# need to import all these to ensure types work as expected
from mytunes.local import *  # type: ignore[import]
from mytunes.local.album import *  # type: ignore[import]
from mytunes.local.artist import *  # type: ignore[import]
from mytunes.local.genre import *  # type: ignore[import]
from mytunes.local.library import *  # type: ignore[import]
from mytunes.local.playlist import *  # type: ignore[import]
from mytunes.local.track import *  # type: ignore[import]
from mytunes.spotify import *  # type: ignore[import]
from mytunes.spotify.album import *  # type: ignore[import]
from mytunes.spotify.artist import *  # type: ignore[import]
from mytunes.spotify.genre import *  # type: ignore[import]
from mytunes.spotify.library import *  # type: ignore[import]
from mytunes.spotify.playlist import *  # type: ignore[import]
from mytunes.spotify.track import *  # type: ignore[import]
from mytunes.spotify.user import *  # type: ignore[import]
from .._models import BaseModel, AttributeModel, ResourceModel  # type: ignore[import]
from .._models.collection import RemoteCollection  # type: ignore[import]
from .._models.collection.album import AlbumCollection, RemoteAlbumCollection  # type: ignore[import]
from .._models.collection.artist import ArtistCollection, RemoteArtistCollection  # type: ignore[import]
from .._models.collection.genre import GenreCollection, RemoteGenreCollection  # type: ignore[import]
from .._models.collection.library import Library, MutableLibrary  # type: ignore[import]
from .._models.collection.library import RemoteLibrary, RemoteMutableLibrary  # type: ignore[import]
from .._models.collection.playlist import Playlist, MutablePlaylist  # type: ignore[import]
from .._models.collection.playlist import RemotePlaylist, RemoteMutablePlaylist  # type: ignore[import]
from .._models.item.album import Album, RemoteAlbum  # type: ignore[import]
from .._models.item.artist import Artist, RemoteArtist  # type: ignore[import]
from .._models.item.genre import Genre, RemoteGenre  # type: ignore[import]
from .._models.item.track import Track, RemoteTrack  # type: ignore[import]
from .._models.item.user import RemoteUser  # type: ignore[import]
from .._models.remote import RemoteResource  # type: ignore[import]

AttributeModel = AttributeModel.annotation
ResourceModel = ResourceModel.annotation

Album = Album.annotation
AlbumCollection = AlbumCollection.annotation
RemoteAlbum = RemoteAlbum.annotation
RemoteAlbumCollection = RemoteAlbumCollection.annotation

Artist = Artist.annotation
ArtistCollection = ArtistCollection.annotation
RemoteArtistCollection = RemoteArtistCollection.annotation

Genre = Genre.annotation
GenreCollection = GenreCollection.annotation
RemoteGenre = RemoteGenre.annotation
RemoteGenreCollection = RemoteGenreCollection.annotation

Track = Track.annotation
RemoteTrack = RemoteTrack.annotation

RemoteUser = RemoteUser.annotation

Library = Library.annotation
MutableLibrary = MutableLibrary.annotation
RemoteLibrary = RemoteLibrary.annotation
RemoteMutableLibrary = RemoteMutableLibrary.annotation

Playlist = Playlist.annotation
MutablePlaylist = MutablePlaylist.annotation
RemotePlaylist = RemotePlaylist.annotation
RemoteMutablePlaylist = RemoteMutablePlaylist.annotation
