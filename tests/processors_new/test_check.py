from collections.abc import Generator
from copy import deepcopy
from unittest.mock import patch, Mock, AsyncMock

import pytest
from faker import Faker
from pytest_mock import MockerFixture

from musify.models.api import RemoteAPI
from musify.models.api.playlist import PlaylistReadWriteEndpoints, PlaylistReadWriteSavedEndpoints
from musify.models.collection import CollectionModel
from musify.models.collection.playlist import RemotePlaylist, Playlist, RemoteMutablePlaylist
from musify.models.item.track import Track, RemoteTrack
from musify.models.user import RemoteUser
from musify.processors_new.check import Checker
from tests.models.api.utils import MockUrlCursor
from tests.models.testers import BaseModelTester
from tests.models.utils import MockRemoteCollection
from tests.utils import SimpleURI


class TestChecker(BaseModelTester):
    @pytest.fixture
    def model(self, api: RemoteAPI) -> Checker:
        return Checker(api=api)

    @pytest.fixture
    def tracks(self, tracks: list[Track], faker: Faker) -> list[RemoteTrack]:
        return [
            RemoteTrack(
                **track.model_dump(),
                uri=SimpleURI.from_id(faker.pystr(22, 22), kind=RemoteTrack.type)
            )
            for track in tracks
        ]

    @pytest.fixture
    def collection(self, collections: list[CollectionModel], faker: Faker) -> CollectionModel:
        return faker.random_element(collections)

    @pytest.fixture
    def collections(self, tracks: list[Track], faker: Faker) -> list[CollectionModel]:
        return [
            MockRemoteCollection(
                name=faker.sentence(),
                cursor=MockUrlCursor(url=faker.url()),
                items=faker.random_elements(tracks),
                uri=SimpleURI.from_id(faker.pystr(22, 22), kind=MockRemoteCollection.type),
            )
            for _ in range(faker.random_int(min=50, max=100))
        ]

    @pytest.fixture
    def playlist(self, playlists: list[RemoteMutablePlaylist], faker: Faker) -> RemoteMutablePlaylist:
        return faker.random_element(playlists)

    @pytest.fixture
    def playlists(self, playlists: list[Playlist], faker: Faker) -> list[RemoteMutablePlaylist]:
        user = RemoteUser(
            name=faker.name(), uri=SimpleURI.from_id(faker.pystr(22, 22), kind=RemoteUser.type)
        )
        return [
            RemoteMutablePlaylist(
                **pl.model_dump(),
                owner=user,
                cursor=MockUrlCursor(url=faker.url()),
                uri=SimpleURI.from_id(faker.pystr(22, 22), kind=RemotePlaylist.type)
            )
            for pl in playlists
        ]

    @pytest.fixture(autouse=True)
    def mock_get_playlist(self, playlist: RemoteMutablePlaylist) -> Generator[Mock, None, None]:
        with patch.object(
                PlaylistReadWriteSavedEndpoints, "get_or_create", return_value=playlist, new_callable=AsyncMock
        ) as mock_get:
            yield mock_get

    @pytest.fixture(autouse=True)
    def mock_create_playlist(self, playlist: RemoteMutablePlaylist) -> Generator[Mock, None, None]:
        with patch.object(
                PlaylistReadWriteSavedEndpoints, "create", return_value=playlist, new_callable=AsyncMock
        ) as mock_create:
            yield mock_create

    @pytest.fixture(autouse=True)
    def mock_follow_playlist(self) -> Generator[Mock, None, None]:
        with patch.object(PlaylistReadWriteSavedEndpoints, "follow", new_callable=AsyncMock) as mock_follow:
            yield mock_follow

    @pytest.fixture(autouse=True)
    def mock_delete_playlist(self) -> Generator[Mock, None, None]:
        with patch.object(PlaylistReadWriteSavedEndpoints, "delete", new_callable=AsyncMock) as mock_delete:
            yield mock_delete

    @pytest.fixture(autouse=True)
    def mock_remove_playlist(self) -> Generator[Mock, None, None]:
        with patch.object(PlaylistReadWriteEndpoints, "remove", new_callable=AsyncMock) as mock_sync:
            yield mock_sync

    @pytest.fixture(autouse=True)
    def mock_sync_playlist(self) -> Generator[Mock, None, None]:
        with patch.object(RemoteMutablePlaylist, "sync_items", new_callable=AsyncMock) as mock_sync:
            yield mock_sync

    async def assert_create_playlist(
            self, model: Checker, playlist: RemoteMutablePlaylist, collection: MockRemoteCollection
    ) -> None:
        assert not model._playlists

        await model._setup_playlist(collection)

        assert list(playlist.tracks) == collection.items

        assert model._playlists == {playlist.uri: playlist}
        assert model._playlists[playlist.uri] is playlist
        assert model._playlists[playlist.uri].tracks == collection.items

        assert model._playlists_initial == {playlist.uri: playlist}
        assert model._playlists_initial[playlist.uri] is not playlist
        assert model._playlists_initial[playlist.uri].tracks != collection.items

    async def test_get_playlist(
            self,
            model: Checker,
            collection: MockRemoteCollection,
            playlist: RemoteMutablePlaylist,
            mock_get_playlist: Mock,
            mock_create_playlist: Mock,
            mock_sync_playlist: Mock,
            mock_follow_playlist: Mock,
            faker: Faker,
    ) -> None:
        playlist_properties = faker.pydict()
        model.playlist_properties = playlist_properties
        model.use_existing_playlists = True

        await self.assert_create_playlist(model, playlist, collection)

        mock_get_playlist.assert_called_once_with(name=collection.name, **playlist_properties)
        mock_create_playlist.assert_not_called()
        mock_sync_playlist.assert_called_once_with(api=model.api, kind="refresh", dry_run=False, show_bar=False)
        mock_follow_playlist.assert_called_once_with(playlist.uri.api_url)

    async def test_create_playlist(
            self,
            model: Checker,
            collection: MockRemoteCollection,
            playlist: RemoteMutablePlaylist,
            mock_get_playlist: Mock,
            mock_create_playlist: Mock,
            mock_sync_playlist: Mock,
            mock_follow_playlist: Mock,
            faker: Faker,
    ) -> None:
        playlist_properties = faker.pydict()
        model.playlist_properties = playlist_properties
        model.use_existing_playlists = False

        await self.assert_create_playlist(model, playlist, collection)

        mock_get_playlist.assert_not_called()
        mock_create_playlist.assert_called_once_with(name=collection.name, **playlist_properties)
        mock_sync_playlist.assert_called_once_with(api=model.api, kind="refresh", dry_run=False, show_bar=False)
        mock_follow_playlist.assert_called_once_with(playlist.uri.api_url)

    async def test_delete_playlist(
            self,
            model: Checker,
            playlist: RemoteMutablePlaylist,
            tracks: list[RemoteTrack],
            mock_sync_playlist: Mock,
            mock_remove_playlist: Mock,
            mock_delete_playlist: Mock,
    ):
        playlist_cleared = deepcopy(playlist)
        playlist_cleared.tracks.clear()

        playlist.tracks.extend(tracks)
        expected_uris = [track.uri for track in tracks]

        assert not playlist_cleared.tracks
        assert playlist.tracks

        model._playlists_initial[playlist.uri] = playlist
        model._playlists[playlist.uri] = playlist

        await model._teardown_playlist(playlist_cleared)

        mock_sync_playlist.assert_not_called()
        mock_remove_playlist.assert_called_once_with(playlist.uri.api_url, uris=expected_uris, show_bar=False)
        mock_delete_playlist.assert_called_once_with(playlist.uri.api_url)

    async def test_restore_playlist(
            self,
            model: Checker,
            playlist: RemoteMutablePlaylist,
            tracks: list[RemoteTrack],
            mock_sync_playlist: Mock,
            mock_remove_playlist: Mock,
            mock_delete_playlist: Mock,
    ):
        playlist.tracks.extend(tracks)

        await model._teardown_playlist(playlist)

        mock_sync_playlist.assert_called_once_with(api=model.api, kind="refresh", dry_run=False, show_bar=False)
        mock_remove_playlist.assert_not_called()
        mock_delete_playlist.assert_not_called()

    @pytest.fixture
    def mock_teardown_playlist(self, model: Checker, mocker: MockerFixture) -> Mock:
        return mocker.spy(model, "_teardown_playlist")

    async def test_teardown_playlists_skips(
            self,
            model: Checker,
            playlists: list[RemoteMutablePlaylist],
            mock_teardown_playlist: Mock,
    ):
        assert not model._playlists_initial
        assert not model._playlists

        await model._teardown_playlists()

        assert not model._playlists_initial
        assert not model._playlists

        mock_teardown_playlist.assert_not_called()

    async def test_teardown_playlists(
            self,
            model: Checker,
            playlists: list[RemoteMutablePlaylist],
            mock_teardown_playlist: Mock,
            faker: Faker,
    ):
        for pl in faker.random_elements(playlists):
            pl.tracks.clear()

        model._playlists = {pl.uri: pl for pl in playlists}
        model._playlists_initial = {pl.uri: pl for pl in playlists}

        await model._teardown_playlists()

        assert not model._playlists_initial
        assert not model._playlists

        assert mock_teardown_playlist.call_count == len(playlists)
