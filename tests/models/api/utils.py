from random import choice
from typing import ClassVar, Self, final
from unittest.mock import patch, Mock

from aiorequestful.auth import Authoriser

from musify.models.api import RemoteAPI, RemoteAuthoriser, ReadSavedEndpoints, HasSavedEndpoints, \
    HasEndpoints
from musify.models.api.album import HasAlbumEndpoints, AlbumEndpoints
from musify.models.api.artist import HasArtistEndpoints, ArtistEndpoints
from musify.models.api.playlist import HasPlaylistEndpoints, PlaylistEndpoints, PlaylistReadSavedEndpoints
from musify.models.api.track import HasTrackEndpoints, TrackEndpoints
from musify.models.api.user import HasUserEndpoints, UserEndpoints
from musify.models.collection import RemoteCollection
from musify.models.collection.playlist import RemotePlaylist
from musify.models.cursors import IndexCursor, UrlCursor
from musify.models.item.album import RemoteAlbum
from musify.models.item.artist import RemoteArtist
from musify.models.item.track import RemoteTrack
from musify.models.remote import RemoteResource
from musify.models.user import RemoteUser
from tests.utils import SimpleURI


class MockRemoteResource(RemoteResource[SimpleURI]):
    source: ClassVar[str] = "mock"
    type: ClassVar[str] = choice((
        RemoteTrack.type,
        RemoteAlbum.type,
        RemoteArtist.type,
    ))

    def reload(self, api: HasEndpoints) -> Self:
        return self


class MockRemoteCollection(MockRemoteResource, RemoteCollection):
    def _items(self) -> list:
        return []

    def extend(self, api: HasEndpoints) -> None:
        pass


@final
class MockIndexCursor(IndexCursor):
    __final__ = True
    source: ClassVar[str] = MockRemoteResource.source


@final
class MockUrlCursor(UrlCursor):
    __final__ = True
    source: ClassVar[str] = MockRemoteResource.source


class MockRemoteAuthoriser(RemoteAuthoriser[Mock]):
    client_id: str = "test_client_id"

    @patch.multiple(
        Authoriser,
        __abstractmethods__=set(),
        authorise=Mock(),
    )
    def create_authoriser(self) -> Authoriser:
        # noinspection PyAbstractClass
        return Authoriser()


class MockUserEndpoints(
    UserEndpoints[SimpleURI, RemoteUser]
):
    pass


class MockTrackEndpoints(
    TrackEndpoints[SimpleURI, RemoteTrack],
    HasSavedEndpoints[ReadSavedEndpoints[SimpleURI, RemoteTrack]],
):
    pass


class MockArtistEndpoints(
    ArtistEndpoints[SimpleURI, RemoteArtist],
    HasSavedEndpoints[ReadSavedEndpoints[SimpleURI, RemoteArtist]],
):
    pass


class MockAlbumEndpoints(
    AlbumEndpoints[SimpleURI, RemoteAlbum],
    HasSavedEndpoints[ReadSavedEndpoints[SimpleURI, RemoteAlbum]],
):
    pass


class MockPlaylistEndpoints(
    PlaylistEndpoints[SimpleURI, RemotePlaylist],
    HasSavedEndpoints[PlaylistReadSavedEndpoints[SimpleURI, RemotePlaylist, RemoteUser]],
):
    pass


class MockRemoteAPI(
    RemoteAPI[MockRemoteAuthoriser],
    HasUserEndpoints[MockUserEndpoints],
    HasTrackEndpoints[MockTrackEndpoints],
    HasArtistEndpoints[MockArtistEndpoints],
    HasAlbumEndpoints[MockAlbumEndpoints],
    HasPlaylistEndpoints[MockPlaylistEndpoints],
):
    pass
