"""Utilities for testing using remote resources."""
import re
from random import choice
from typing import final, Self, Callable, Any, ClassVar
from unittest.mock import Mock, patch, MagicMock

from aiorequestful.auth import Authoriser
from faker import Faker
from mytunes._models import ResourceModel
from mytunes._models.api import HasEndpoints, RemoteAuthoriser, BatchReadAllEndpoints, BatchWriteEndpoints, \
    BatchReadEndpoints, HasLibraryEndpoints, RemoteAPI
from mytunes._models.api.items import HasTrackEndpoints, HasArtistEndpoints, HasAlbumEndpoints
from mytunes._models.api.playlist import PlaylistLibraryEndpoints, PlaylistReadWriteEndpoints, HasPlaylistEndpoints
from mytunes._models.api.search import SearchEndpoints, HasSearchEndpoints
from mytunes._models.api.user import UserEndpoints, HasUserEndpoints
from mytunes._models.collection import RemoteCollection
from mytunes._models.collection.playlist import Playlist, RemotePlaylist
from mytunes._models.cursors import IndexCursor, KeyCursor, UrlCursor
from mytunes._models.item.album import Album, RemoteAlbum
from mytunes._models.item.artist import Artist, RemoteArtist
from mytunes._models.item.track import Track, RemoteTrack
from mytunes._models.item.user import RemoteUser
from mytunes._models.properties.name import HasName
from mytunes._models.properties.uri import URI
from mytunes._models.remote import RemoteResource
from pydantic import Field, AliasPath, PositiveInt
from yarl import URL


class CallbackResult:
    def __init__(self, method: str = "GET", status: int = 200, body: str | bytes = ''):
        self.method = method
        self.status = status
        self.body = body

    async def read(self) -> bytes:
        return self.body

    def __await__(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

    @classmethod
    def from_response(cls, body: str | bytes) -> Callable[[Any], Self]:
        return lambda *_, **__: CallbackResult(body=body)


@final
class SimpleURI(URI):
    __final__ = True
    _source = "remote"

    @property
    def source(self) -> str:
        return self.root.split(":")[0]

    @property
    def type(self) -> str:
        return self.root.split(":")[1]

    @property
    def id(self) -> str:
        return self.root.split(":")[2]

    @classmethod
    def create_random(cls, kind: str | None = None) -> Self:
        if not kind:
            kind = choice((Track.type, Album.type, Artist.type, Playlist.type))
        value = Faker().pystr()
        return cls.from_id(value=value, kind=kind)

    @classmethod
    def create_unavailable(cls, kind: str) -> Self:
        return cls.from_id(value=cls._unavailable_id, kind=kind)

    @classmethod
    def from_id[T](cls, value: T, kind: str) -> T | Self:
        uri = ":".join((cls._source, kind, str(value)))
        return cls(uri)

    @property
    def api_url(self) -> URL:
        return URL.build(scheme="https", host="api.example.com", path=f"/{self.type}/{self.id}")

    @classmethod
    def from_api_url[T](cls, value: T) -> T | str:
        return cls.from_public_url(value)

    @property
    def public_url(self) -> URL:
        return URL.build(scheme="https", host="example.com", path=f"/{self.type}/{self.id}")

    @classmethod
    def from_public_url[T](cls, value: T) -> T | str:
        if isinstance(value, str) and re.match(r"^https://(api.)?example\.com", value):
            value = URL(value)
        if not isinstance(value, URL):
            return value

        return ":".join((cls._source, *value.path.lstrip("/").split("/")[-2:]))


class MockRemoteResource(RemoteResource[SimpleURI]):
    source: ClassVar[str] = "remote"
    type: ClassVar[str] = choice((
        RemoteTrack.type,
        RemoteAlbum.type,
        RemoteArtist.type,
    ))

    async def reload(self, api: HasEndpoints) -> None:
        pass


class MockRemoteCollection(MockRemoteResource, RemoteCollection, HasName):
    type: ClassVar[str] = MockRemoteResource.type

    name: str = "test"
    all_items: list = Field(default_factory=list)

    @property
    def _items(self) -> list:
        return self.all_items

    def _clear(self) -> None:
        self.all_items.clear()

    async def extend(self, api: HasEndpoints) -> None:
        pass


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
    PlaylistLibraryEndpoints[SimpleURI, RemotePlaylist, RemoteUser],
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
