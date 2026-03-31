from copy import deepcopy
from typing import Generator, Sequence, Any
from unittest.mock import Mock, patch, AsyncMock

import pytest
from faker import Faker
from pytest_mock import MockerFixture

from musify.exception import MusifyError
from musify.models.api import RemoteAPI
from musify.models.api.playlist import PlaylistReadWriteEndpoints
from musify.models.collection import CollectionModel
from musify.models.collection.playlist import RemoteMutablePlaylist
from musify.models.item.track import RemoteTrack
from musify.models.properties.order import Position
# noinspection PyProtectedMember
from musify.processors.check._page import CheckerPage
from musify.processors.formatter import CollectionFormatter
from tests.models.testers import BaseModelTester
from tests.processors.utils import MockCollection


@pytest.fixture
def model(position: Position, api: RemoteAPI, collections: Sequence[CollectionModel]) -> CheckerPage:
    return CheckerPage(position=position, api=api, collections=collections)


class TestPlaylistManagement(BaseModelTester):
    @pytest.fixture
    def model(self, model: CheckerPage) -> CheckerPage:
        return model

    @pytest.fixture
    def playlist_properties(self, model: CheckerPage, faker: Faker) -> dict[str, Any]:
        properties = faker.pydict()
        properties.pop("name", None)  # name is not allowed as a key
        model.additional_properties = properties
        return properties

    async def assert_create_playlist(
            self, model: CheckerPage, collection: MockCollection, playlist: RemoteMutablePlaylist
    ) -> None:
        assert not model._playlists

        await model._setup_playlist(collection)

        assert model._collections == {playlist.uri: collection}
        assert model._collections[playlist.uri] is collection

        assert model._playlists == {playlist.uri: playlist}
        assert model._playlists[playlist.uri] is playlist

        assert model._playlists_initial == {playlist.uri: playlist}
        assert model._playlists_initial[playlist.uri] is not playlist

    ###########################################################################
    ## Tests
    ###########################################################################
    async def test_get_playlist(
            self,
            model: CheckerPage,
            collection: MockCollection,
            playlists: list[RemoteMutablePlaylist],
            tracks: list[RemoteTrack],
            playlist_properties: dict[str, Any],
            mock_get_playlist: Mock,
            mock_create_playlist: Mock,
            mock_sync_playlist: Mock,
            mock_follow_playlist: Mock,
    ) -> None:
        model.use_existing_playlists = True

        playlist = next(pl for pl in playlists if pl.name.casefold() == collection.name.casefold())
        playlist.tracks.replace(tracks)
        await self.assert_create_playlist(model, playlist=playlist, collection=collection)

        mock_get_playlist.assert_called_once_with(name=collection.name, **playlist_properties)
        mock_create_playlist.assert_not_called()
        mock_sync_playlist.assert_called_once_with(api=model.api, kind="refresh", dry_run=False, show_bar=False)
        mock_follow_playlist.assert_called_once_with(playlist.uri.api_url)

    async def test_create_playlist(
            self,
            model: CheckerPage,
            collection: MockCollection,
            playlists: list[RemoteMutablePlaylist],
            playlist_properties: dict[str, Any],
            mock_get_playlist: Mock,
            mock_create_playlist: Mock,
            mock_sync_playlist: Mock,
            mock_follow_playlist: Mock,
    ) -> None:
        model.use_existing_playlists = False

        playlist = next(pl for pl in playlists if pl.name.casefold() == collection.name.casefold())
        await self.assert_create_playlist(model, playlist=playlist, collection=collection)

        mock_get_playlist.assert_not_called()
        mock_create_playlist.assert_called_once_with(name=collection.name, **playlist_properties)
        mock_sync_playlist.assert_not_called()  # playlist was created so no need to empty it
        mock_follow_playlist.assert_called_once_with(playlist.uri.api_url)

    async def test_delete_playlist(
            self,
            model: CheckerPage,
            playlist: RemoteMutablePlaylist,
            collection: CollectionModel,
            tracks: list[RemoteTrack],
            mock_sync_playlist: Mock,
            mock_delete_playlist: Mock,
    ):
        playlist_cleared = deepcopy(playlist)
        playlist_cleared.tracks.clear()
        playlist.tracks.extend(tracks)

        assert not playlist_cleared.tracks
        assert playlist.tracks

        model._collections[playlist.uri] = collection
        model._playlists[playlist.uri] = playlist
        model._playlists_initial[playlist.uri] = playlist_cleared

        await model._teardown_playlist(playlist)

        assert not playlist_cleared.tracks

        mock_sync_playlist.assert_not_called()
        mock_delete_playlist.assert_called_once_with(playlist.uri.api_url)

        assert playlist.uri not in model._collections
        assert playlist.uri not in model._playlists
        assert playlist.uri not in model._playlists_initial

    async def test_restore_playlist(
            self,
            model: CheckerPage,
            playlist: RemoteMutablePlaylist,
            collection: CollectionModel,
            tracks: list[RemoteTrack],
            mock_sync_playlist: Mock,
            mock_delete_playlist: Mock,
    ):
        playlist_cleared = deepcopy(playlist)
        playlist_cleared.tracks.clear()
        playlist.tracks.extend(tracks)

        model._collections[playlist.uri] = collection
        model._playlists[playlist.uri] = playlist_cleared
        model._playlists_initial[playlist.uri] = playlist

        await model._teardown_playlist(playlist)

        mock_sync_playlist.assert_called_once_with(api=model.api, kind="refresh", dry_run=False, show_bar=False)
        mock_delete_playlist.assert_not_called()

        assert playlist.uri not in model._collections
        assert playlist.uri not in model._playlists
        assert playlist.uri not in model._playlists_initial

    async def test_setup_playlists_fails(
            self,
            model: CheckerPage,
            playlists: list[RemoteMutablePlaylist],
            collections: list[CollectionModel],
            mocker: MockerFixture,
    ):
        mock_teardown_playlists = mocker.spy(CheckerPage, "teardown_playlists")

        with patch.object(model, "_setup_playlist", side_effect=MusifyError):
            with pytest.raises(MusifyError):
                await model.setup_playlists()
            mock_teardown_playlists.assert_called_once()

    @pytest.fixture
    def mock_teardown_playlist(self, model: CheckerPage, mocker: MockerFixture) -> Mock:
        return mocker.spy(model, "_teardown_playlist")

    async def test_teardown_playlists_skips(
            self,
            model: CheckerPage,
            playlists: list[RemoteMutablePlaylist],
            mock_teardown_playlist: Mock,
    ):
        assert not model._collections
        assert not model._playlists
        assert not model._playlists_initial

        await model.teardown_playlists()

        assert not model._collections
        assert not model._playlists
        assert not model._playlists_initial

        mock_teardown_playlist.assert_not_called()

    async def test_teardown_playlists(
            self,
            model: CheckerPage,
            playlists: list[RemoteMutablePlaylist],
            collections: list[CollectionModel],
            mock_teardown_playlist: Mock,
            faker: Faker,
    ):
        for pl in faker.random_elements(playlists, unique=True):
            pl.tracks.clear()

        model._collections = {pl.uri: coll for pl, coll in zip(playlists, collections)}
        model._playlists = {pl.uri: pl for pl in playlists}
        model._playlists_initial = {pl.uri: pl for pl in playlists}

        await model.teardown_playlists()

        assert not model._collections
        assert not model._playlists
        assert not model._playlists_initial

        assert mock_teardown_playlist.call_count == len(playlists)

    ###########################################################################
    ## State getters
    ###########################################################################
    def test_basic_getters(
            self,
            model: CheckerPage,
            playlist: RemoteMutablePlaylist,
            collection: CollectionModel,
            tracks: list[RemoteTrack],
            faker: Faker,
    ):
        playlist.tracks.replace(tracks)

        playlist_initial = deepcopy(playlist)
        playlist_initial.tracks.replace(faker.random_elements(tracks))

        model._collections[playlist.uri] = collection
        model._playlists[playlist.uri] = playlist
        model._playlists_initial[playlist.uri] = playlist_initial

        assert model.get_collection_items(playlist.uri) == list(collection.items)

        assert model.get_playlist_name(playlist.uri) == playlist.name
        assert model.get_stored_playlist_items(playlist.uri) == list(playlist.items)
        assert model.get_initial_playlist_items(playlist.uri) == list(playlist_initial.items)

    async def test_get_current_playlist_items(
            self,
            model: CheckerPage,
            playlist: RemoteMutablePlaylist,
            collection: CollectionModel,
            tracks: list[RemoteTrack],
            mock_get_playlist_items: Mock,
    ):
        result = await model.get_current_playlist_items(playlist.uri)

        assert result == tracks
        mock_get_playlist_items.assert_called_once_with(playlist)

    async def test_refresh_playlist_items(
            self,
            model: CheckerPage,
            playlist: RemoteMutablePlaylist,
            tracks: list[RemoteTrack],
            mock_get_playlist_items: Mock,
            faker: Faker,
    ):
        initial = faker.random_elements(tracks, length=len(tracks) // 2, unique=True)
        playlist.tracks.replace(initial)
        model._playlists[playlist.uri] = playlist

        await model.refresh_playlist_items(playlist.uri)
        assert playlist.count != len(initial)
        assert playlist.tracks != initial


class TestPausePages:
    @pytest.fixture
    def model(
        self,
        model: CheckerPage,
        playlists: list[RemoteMutablePlaylist],
        collections: list[CollectionModel],
    ) -> CheckerPage:
        model._collections = {pl.uri: coll for pl, coll in zip(playlists, collections)}
        model._playlists = {pl.uri: pl for pl in playlists}
        model._playlists_initial = {pl.uri: deepcopy(pl) for pl in playlists}

        return model

    @pytest.fixture
    def mock_get_playlist_items(self, tracks: list[RemoteTrack], faker: Faker) -> Generator[Mock, None, None]:
        def _random_tracks(*_, **__) -> Sequence[RemoteTrack]:
            return faker.random_elements(tracks)

        with patch.object(
                PlaylistReadWriteEndpoints, "get_all", side_effect=_random_tracks, new_callable=AsyncMock
        ) as mock_get_all:
            yield mock_get_all

    async def test_print_playlist_items_no_changes(
            self,
            model: CheckerPage,
            playlist: RemoteMutablePlaylist,
            mock_get_playlist_items: Mock,
            mocker: MockerFixture,
            faker: Faker,
    ):
        mock_format = mocker.spy(CollectionFormatter, "format")
        mock_get_playlist_items.reset_mock(side_effect=True)
        mock_get_playlist_items.return_value = playlist.tracks

        await model._print_playlist_items(playlist)
        mock_format.assert_called_once_with(model.formatter, playlist, indices=True)

    async def test_print_playlist_items_with_changes(
            self,
            model: CheckerPage,
            playlist: RemoteMutablePlaylist,
            tracks: list[RemoteTrack],
            mock_get_playlist_items: Mock,
            mocker: MockerFixture,
            faker: Faker,
    ):
        mock_format = mocker.spy(CollectionFormatter, "format")

        await model._print_playlist_items(playlist)
        assert mock_format.call_count == 2
