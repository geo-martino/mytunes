from typing import ClassVar, final, Any
from unittest.mock import patch, Mock, MagicMock

from aiorequestful.auth import Authoriser
from pydantic import PositiveInt, AliasPath
from yarl import URL

from musify.models import ResourceModel
from musify.models.api import RemoteAPI, RemoteAuthoriser, HasLibraryEndpoints, BatchReadAllEndpoints, \
    BatchWriteEndpoints, BatchReadEndpoints
from musify.models.api.items import HasAlbumEndpoints, HasArtistEndpoints, HasTrackEndpoints
from musify.models.api.playlist import HasPlaylistEndpoints, PlaylistReadWriteEndpoints, PlaylistLibraryEndpoints
from musify.models.api.search import SearchEndpoints, HasSearchEndpoints
from musify.models.api.user import HasUserEndpoints, UserEndpoints
from musify.models.collection.playlist import RemotePlaylist
from musify.models.cursors import IndexCursor, UrlCursor, KeyCursor
from musify.models.item.album import RemoteAlbum
from musify.models.item.artist import RemoteArtist
from musify.models.item.track import RemoteTrack
from musify.models.remote import RemoteResource
from musify.models.user import RemoteUser
from tests.models.utils import MockRemoteResource
from tests.utils import SimpleURI


@final
class MockIndexCursor(IndexCursor):
    __final__ = True
    source: ClassVar[str] = MockRemoteResource.source


@final
class MockKeyCursor(KeyCursor):
    __final__ = True
    source: ClassVar[str] = MockRemoteResource.source


@final
class MockUrlCursor(UrlCursor):
    __final__ = True
    source: ClassVar[str] = MockRemoteResource.source


@final
class MockInitialCursor(UrlCursor):
    __final__ = True
    source: ClassVar[str] = MockRemoteResource.source


class MockRemoteAuthoriser(RemoteAuthoriser[Mock]):
    source: ClassVar[str] = MockRemoteResource.source

    client_id: str = "test_client_id"

    @patch.multiple(
        Authoriser,
        __abstractmethods__=set(),
        authorise=MagicMock(),
    )
    def create_authoriser(self) -> Authoriser:
        # noinspection PyAbstractClass
        return Authoriser()


class MockUserEndpoints(
    UserEndpoints[SimpleURI, RemoteUser]
):
    _me_url = "https://api.example.com/v1/me"


class MockSearchEndpoints(
    SearchEndpoints[SimpleURI, RemoteTrack | RemoteAlbum | RemoteUser, ResourceModel]
):
    _query_url = URL("https://api.example.com/search")
    _query_path = AliasPath("items", "{type}s")
    _query_limit = 22

    def _format_query_params(
            self, query: str, types: set, limit: PositiveInt | None = None, **kwargs
    ) -> dict[str, Any]:
        pass

    def _format_query_from_item(self, item: ResourceModel, **kwargs) -> dict[str, Any]:
        pass


class MockLibraryEndpoints[RT: RemoteResource](
    BatchReadAllEndpoints[SimpleURI, RT],
    BatchWriteEndpoints[SimpleURI, RT],
):
    pass


class MockItemEndpoints[RT: RemoteResource](
    BatchReadEndpoints[SimpleURI, RT],
    HasLibraryEndpoints[MockLibraryEndpoints[RT]],
):
    pass


class MockPlaylistLibraryEndpoints(
    PlaylistLibraryEndpoints[SimpleURI, RemotePlaylist, RemoteTrack, RemoteUser],
):
    pass


class MockPlaylistEndpoints(
    PlaylistReadWriteEndpoints[SimpleURI, RemotePlaylist, RemoteTrack],
    HasLibraryEndpoints[MockPlaylistLibraryEndpoints],
):
    pass


class MockRemoteAPI(
    RemoteAPI[MockRemoteAuthoriser],
    HasUserEndpoints[MockUserEndpoints],
    HasSearchEndpoints[MockSearchEndpoints],
    HasTrackEndpoints[MockItemEndpoints[RemoteTrack]],
    HasArtistEndpoints[MockItemEndpoints[RemoteArtist]],
    HasAlbumEndpoints[MockItemEndpoints[RemoteAlbum]],
    HasPlaylistEndpoints[MockPlaylistEndpoints],
):
    source: ClassVar[str] = MockRemoteAuthoriser.source
