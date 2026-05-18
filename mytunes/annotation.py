# need to import all these to ensure types work as expected
from mytunes.local import *  # type: ignore[import]
from mytunes.local.album import *  # type: ignore[import]
from mytunes.local.artist import *  # type: ignore[import]
from mytunes.local.genre import *  # type: ignore[import]
from mytunes.local.library import *  # type: ignore[import]
from mytunes.local.playlist import *  # type: ignore[import]
from mytunes.local.track import *  # type: ignore[import]
from mytunes.core.properties.uri import URI
from mytunes.spotify import *  # type: ignore[import]
from mytunes.spotify.album import *  # type: ignore[import]
from mytunes.spotify.artist import *  # type: ignore[import]
from mytunes.spotify.genre import *  # type: ignore[import]
from mytunes.spotify.library import *  # type: ignore[import]
from mytunes.spotify.playlist import *  # type: ignore[import]
from mytunes.spotify.track import *  # type: ignore[import]
from mytunes.spotify.user import *  # type: ignore[import]
# already annotations
from mytunes._types import Character, StrippedCharacter, String, StrippedString  # type: ignore[import]
from mytunes._types import LowerStrippedString, UpperStrippedString  # type: ignore[import]
from mytunes._types import LowerSnakeCase, UpperSnakeCase, ListWithValues  # type: ignore[import]
from mytunes._types import Number, ListWithValues  # type: ignore[import]
from mytunes._types import TO_SET, TO_TUPLE, TO_LIST, DEFAULT_IF_NONE, HttpURL  # type: ignore[import]
# types to be converted to annotations
from ._base import BaseModel
from ._base.attribute import AttributeModel
from ._base.resource import ResourceModel
from mytunes.core.collection import RemoteCollection
from mytunes.core.album import AlbumCollection, RemoteAlbumCollection
from mytunes.core.artist import ArtistCollection, RemoteArtistCollection
from mytunes.core.genre import GenreCollection, RemoteGenreCollection
from mytunes.core.library import Library, MutableLibrary
from mytunes.core.library import RemoteLibrary, RemoteMutableLibrary
from mytunes.core.playlist import Playlist, MutablePlaylist
from mytunes.core.playlist import RemotePlaylist, RemoteMutablePlaylist
from mytunes.core.album import Album, RemoteAlbum
from mytunes.core.artist import Artist, RemoteArtist
from mytunes.core.genre import Genre, RemoteGenre
from mytunes.core.track import Track, RemoteTrack
from mytunes.core.user import User, RemoteUser
from mytunes.core.remote import RemoteModel, RemoteResource

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
