from collections.abc import Generator
from unittest.mock import patch, Mock, AsyncMock

import pytest
from faker import Faker
from yarl import URL

from mytunes.core._collection import CollectionModel
from mytunes.core._collection.playlist import RemotePlaylist, Playlist, RemoteMutablePlaylist
from mytunes.core._item.genre import Genre
from mytunes.core._item.track import Track, RemoteTrack
from mytunes.core._item.user import RemoteUser
from mytunes.core.api import BatchWriteEndpoints
from mytunes.core.api.playlist import PlaylistReadWriteEndpoints, PlaylistLibraryEndpoints
from mytunes.core.cursors import InitialCursor
from mytunes.core.properties.order import Position
from mytunes.core.properties.uri import HasImmutableURI, HasMutableURI, HasURI
from tests.processors.check._playlist.utils import HasNameAndImmutableURI, HasNameAndMutableURI
from tests.processors.utils import MockCollection
from tests.remote import SimpleURI, MockUrlCursor, MockInitialCursor


@pytest.fixture
def tracks(tracks: list[Track], faker: Faker) -> list[RemoteTrack]:
    return [
        RemoteTrack(
            **track.model_dump(),
            uri=SimpleURI.create_random(RemoteTrack.type))
        for track in tracks
    ]


@pytest.fixture
def collections(
        playlists: list[RemoteMutablePlaylist], tracks: list[Track], faker: Faker
) -> list[CollectionModel]:
    return [
        MockCollection(
            name=pl.name,
            all_items=list(faker.random_elements(tracks)),
        )
        for pl in playlists
    ]


@pytest.fixture
def playlists(playlists: list[Playlist], faker: Faker) -> list[RemoteMutablePlaylist]:
    user = RemoteUser(
        name=faker.name(), uri=SimpleURI.create_random(RemoteUser.type)
    )
    return [
        RemoteMutablePlaylist(
            **pl.model_dump(),
            owner=user,
            cursor=MockUrlCursor(url=URL(faker.url())),
            uri=SimpleURI.create_random(RemotePlaylist.type),
        )
        for pl in playlists
    ]


@pytest.fixture
def available_items(faker: Faker) -> list[HasImmutableURI]:
    return [
        HasNameAndImmutableURI(name=faker.name(), uri=SimpleURI.create_random(Track.type))
        for _ in range(faker.random_int(10, 30))
    ]


@pytest.fixture
def mutable_items(faker: Faker) -> list[HasMutableURI]:
    return [
        HasNameAndMutableURI(name=faker.name(), uri=SimpleURI.create_random(Track.type))
        for _ in range(faker.random_int(10, 30))
    ]


@pytest.fixture
def unavailable_items(faker: Faker) -> list[HasMutableURI]:
    return [
        HasNameAndMutableURI(name=faker.name(), uri=SimpleURI.create_unavailable(Track.type))
        for _ in range(faker.random_int(5, 20))
    ]


@pytest.fixture
def missing_items(faker: Faker) -> list[HasMutableURI]:
    missing = [
        HasNameAndMutableURI(name=faker.name(), uri=None)
        for _ in range(faker.random_int(10, 30))
    ]

    return missing


@pytest.fixture
def invalid_items(faker: Faker) -> list[Genre]:
    return [Genre(name=faker.name()) for _ in range(faker.random_int(5, 20))]


@pytest.fixture
def position(faker: Faker) -> Position:
    count = faker.random_int(1, 100)
    total = faker.random_int(count, 101)
    return Position(number=count, total=total)


@pytest.fixture(autouse=True)
def mock_get(playlists: list[RemoteMutablePlaylist]) -> Generator[Mock]:
    def _get_playlist(url: URL, *_, **__) -> RemoteMutablePlaylist | None:
        return next((pl for pl in playlists if pl.uri.api_url == url), None)

    with patch.object(
            PlaylistReadWriteEndpoints, "get", side_effect=_get_playlist, new_callable=AsyncMock
    ) as mock_get:
        yield mock_get


@pytest.fixture(autouse=True)
def mock_get_playlist(playlists: list[RemoteMutablePlaylist]) -> Generator[Mock]:
    def _get_playlist(name: str, *_, **__) -> RemoteMutablePlaylist | None:
        return next((pl for pl in playlists if pl.name.casefold() == name.casefold()), None)

    with patch.object(
            PlaylistLibraryEndpoints, "get_or_create", side_effect=_get_playlist, new_callable=AsyncMock
    ) as mock_get:
        yield mock_get


@pytest.fixture(autouse=True)
def mock_create_playlist(playlists: list[RemoteMutablePlaylist]) -> Generator[Mock]:
    def _get_playlist(name: str, *_, **__) -> RemoteMutablePlaylist | None:
        return next((pl for pl in playlists if pl.name.casefold() == name.casefold()), None)

    with patch.object(
            PlaylistLibraryEndpoints, "create", side_effect=_get_playlist, new_callable=AsyncMock
    ) as mock_create:
        yield mock_create


@pytest.fixture(autouse=True)
def mock_add_playlists() -> Generator[Mock]:
    with patch.object(BatchWriteEndpoints, "add_many", new_callable=AsyncMock) as mock_add:
        yield mock_add


@pytest.fixture(autouse=True)
def mock_remove_playlists() -> Generator[Mock]:
    with patch.object(BatchWriteEndpoints, "remove_many", new_callable=AsyncMock) as mock_remove:
        yield mock_remove


@pytest.fixture(autouse=True)
def mock_add() -> Generator[Mock]:
    with patch.object(PlaylistReadWriteEndpoints, "add", new_callable=AsyncMock) as mock_add:
        yield mock_add


@pytest.fixture(autouse=True)
def mock_sync_playlist() -> Generator[Mock]:
    with patch.object(RemoteMutablePlaylist, "sync_items", new_callable=AsyncMock) as mock_sync:
        yield mock_sync


@pytest.fixture(autouse=True)
def mock_get_playlist_items(available_items: list[HasURI], faker: Faker) -> Generator[Mock]:
    with patch.object(
            PlaylistReadWriteEndpoints, "get_all_items", return_value=available_items, new_callable=AsyncMock
    ) as mock_get_all:
        yield mock_get_all


@pytest.fixture(autouse=True)
def mock_initial_cursor_from_url() -> Generator[Mock]:
    def _from_url(url: URL, *_, **__) -> MockInitialCursor:
        return MockInitialCursor(url=url)

    with patch.object(InitialCursor, "from_url", side_effect=_from_url) as mock_from_url:
        yield mock_from_url
