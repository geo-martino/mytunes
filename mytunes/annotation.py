# need to import all these to ensure types work as expected
from mytunes.local import *  # type: ignore[import]
from mytunes.local.album import *  # type: ignore[import]
from mytunes.local.artist import *  # type: ignore[import]
from mytunes.local.genre import *  # type: ignore[import]
from mytunes.local.library import *  # type: ignore[import]
from mytunes.local.playlist import *  # type: ignore[import]
from mytunes.local.track import *  # type: ignore[import]
from mytunes.properties.uri import URI
from mytunes.spotify import *  # type: ignore[import]
from mytunes.spotify.album import *  # type: ignore[import]
from mytunes.spotify.artist import *  # type: ignore[import]
from mytunes.spotify.genre import *  # type: ignore[import]
from mytunes.spotify.library import *  # type: ignore[import]
from mytunes.spotify.playlist import *  # type: ignore[import]
from mytunes.spotify.track import *  # type: ignore[import]
from mytunes.spotify.user import *  # type: ignore[import]
# types to be converted to annotations
from ._base import BaseModel
from ._base.attribute import AttributeModel
from ._base.resource import ResourceModel
from .core.collection import RemoteCollection
from .core.album import AlbumCollection, RemoteAlbumCollection
from .core.artist import ArtistCollection, RemoteArtistCollection
from .core.genre import GenreCollection, RemoteGenreCollection
from .core.library import Library, MutableLibrary
from .core.library import RemoteLibrary, RemoteMutableLibrary
from .core.playlist import Playlist, MutablePlaylist
from .core.playlist import RemotePlaylist, RemoteMutablePlaylist
from .core.album import Album, RemoteAlbum
from .core.artist import Artist, RemoteArtist
from .core.genre import Genre, RemoteGenre
from .core.track import Track, RemoteTrack
from .core.user import User, RemoteUser
from .core.remote import RemoteModel, RemoteResource

BaseModel = BaseModel.annotation
AttributeModel = AttributeModel.annotation
ResourceModel = ResourceModel.annotation

RemoteModel = RemoteModel.annotation
RemoteResource = RemoteResource.annotation
RemoteCollection = RemoteCollection.annotation

Album = Album.annotation
AlbumCollection = AlbumCollection.annotation
RemoteAlbum = RemoteAlbum.annotation
RemoteAlbumCollection = RemoteAlbumCollection.annotation

Artist = Artist.annotation
ArtistCollection = ArtistCollection.annotation
RemoteArtist = RemoteArtist.annotation
RemoteArtistCollection = RemoteArtistCollection.annotation

Genre = Genre.annotation
GenreCollection = GenreCollection.annotation
RemoteGenre = RemoteGenre.annotation
RemoteGenreCollection = RemoteGenreCollection.annotation

Track = Track.annotation
RemoteTrack = RemoteTrack.annotation

User = User.annotation
RemoteUser = RemoteUser.annotation

Library = Library.annotation
MutableLibrary = MutableLibrary.annotation
RemoteLibrary = RemoteLibrary.annotation
RemoteMutableLibrary = RemoteMutableLibrary.annotation

Playlist = Playlist.annotation
MutablePlaylist = MutablePlaylist.annotation
RemotePlaylist = RemotePlaylist.annotation
RemoteMutablePlaylist = RemoteMutablePlaylist.annotation

URI = URI.annotation
