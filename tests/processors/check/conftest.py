from collections.abc import Generator
from unittest.mock import patch, Mock, AsyncMock

import pytest
from faker import Faker
from mytunes._models.api.playlist import PlaylistReadWriteEndpoints, PlaylistLibraryEndpoints, \
    PlaylistBatchWriteEndpoints
from mytunes._models.collection import CollectionModel
from mytunes._models.collection.playlist import RemotePlaylist, Playlist, RemoteMutablePlaylist
from mytunes._models.cursors import InitialCursor
from mytunes._models.item.track import Track, RemoteTrack
from mytunes._models.item.user import RemoteUser
from mytunes._models.properties.order import Position
from mytunes.processors.match import Matcher
from mytunes.processors.score import NameScorer
from tests.processors.utils import MockCollection
from tests.remote import SimpleURI, MockUrlCursor, MockInitialCursor
from yarl import URL


@pytest.fixture
def tracks(tracks: list[Track], faker: Faker) -> list[RemoteTrack]:
    return [
        RemoteTrack(
            **track.model_dump(),
            uri=SimpleURI.create_random(RemoteTrack.type))
        for track in tracks
    ]


@pytest.fixture
def collection(collections: list[CollectionModel], faker: Faker) -> CollectionModel:
    return faker.random_element(collections)


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
            cursor=MockUrlCursor(url=faker.url()),
            uri=SimpleURI.create_random(RemotePlaylist.type),
        )
        for pl in playlists
    ]


@pytest.fixture
def playlist(playlists: list[RemoteMutablePlaylist], faker: Faker) -> RemoteMutablePlaylist:
    return faker.random_element(playlists)


@pytest.fixture
def position(faker: Faker) -> Position:
    count = faker.random_int(1, 100)
    total = faker.random_int(count, 101)
    return Position(number=count, total=total)


@pytest.fixture
def matcher() -> Matcher:
    return Matcher(scorers=[NameScorer()])


@pytest.fixture(autouse=True)
def mock_get(playlists: list[RemoteMutablePlaylist]) -> Generator[Mock, None, None]:
    def _get_playlist(url: URL, *_, **__) -> RemoteMutablePlaylist | None:
        return next((pl for pl in playlists if pl.uri.api_url == url), None)

    with patch.object(
            PlaylistReadWriteEndpoints, "get", side_effect=_get_playlist, new_callable=AsyncMock
    ) as mock_get:
        yield mock_get


@pytest.fixture(autouse=True)
def mock_get_playlist(playlists: list[RemoteMutablePlaylist]) -> Generator[Mock, None, None]:
    def _get_playlist(name: str, *_, **__) -> RemoteMutablePlaylist | None:
        return next((pl for pl in playlists if pl.name.casefold() == name.casefold()), None)

    with patch.object(
            PlaylistLibraryEndpoints, "get_or_create", side_effect=_get_playlist, new_callable=AsyncMock
    ) as mock_get:
        yield mock_get


@pytest.fixture(autouse=True)
def mock_create_playlist(playlists: list[RemoteMutablePlaylist]) -> Generator[Mock, None, None]:
    def _get_playlist(name: str, *_, **__) -> RemoteMutablePlaylist | None:
        return next((pl for pl in playlists if pl.name.casefold() == name.casefold()), None)

    with patch.object(
            PlaylistLibraryEndpoints, "create", side_effect=_get_playlist, new_callable=AsyncMock
    ) as mock_create:
        yield mock_create


@pytest.fixture(autouse=True)
def mock_add_playlists() -> Generator[Mock, None, None]:
    with patch.object(PlaylistBatchWriteEndpoints, "add_many", new_callable=AsyncMock) as mock_add:
        yield mock_add


@pytest.fixture(autouse=True)
def mock_remove_playlists() -> Generator[Mock, None, None]:
    with patch.object(PlaylistBatchWriteEndpoints, "remove_many", new_callable=AsyncMock) as mock_remove:
        yield mock_remove


@pytest.fixture(autouse=True)
def mock_add() -> Generator[Mock, None, None]:
    with patch.object(PlaylistReadWriteEndpoints, "add", new_callable=AsyncMock) as mock_add:
        yield mock_add


@pytest.fixture(autouse=True)
def mock_sync_playlist() -> Generator[Mock, None, None]:
    with patch.object(RemoteMutablePlaylist, "sync_items", new_callable=AsyncMock) as mock_sync:
        yield mock_sync


@pytest.fixture(autouse=True)
def mock_get_playlist_items(tracks: list[RemoteTrack], faker: Faker) -> Generator[Mock, None, None]:
    with patch.object(
            PlaylistReadWriteEndpoints, "get_all", return_value=tracks, new_callable=AsyncMock
    ) as mock_get_all:
        yield mock_get_all


@pytest.fixture(autouse=True)
def mock_initial_cursor_from_url() -> Generator[Mock, None, None]:
    def _from_url(url: URL, *_, **__) -> MockInitialCursor:
        return MockInitialCursor(url=url)

    with patch.object(InitialCursor, "from_url", side_effect=_from_url) as mock_from_url:
        yield mock_from_url
