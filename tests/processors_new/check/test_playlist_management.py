from copy import deepcopy
from typing import Generator, Any
from unittest.mock import Mock, patch, AsyncMock

import pytest
from faker import Faker
from pytest_mock import MockerFixture

from musify.models.api import RemoteAPI
from musify.models.api.playlist import PlaylistReadWriteEndpoints
from musify.models.collection import CollectionModel
from musify.models.collection.playlist import RemoteMutablePlaylist
from musify.models.item.track import Track, RemoteTrack
from musify.processors_new.check import Checker
from tests.models.api.utils import MockUrlCursor
from tests.processors_new.utils import MockCollection
from tests.utils import SimpleURI


class TestPlaylistManagement:
    @pytest.fixture
    def model(self, api: RemoteAPI) -> Checker:
        return Checker(api=api)

    @pytest.fixture
    def collection(self, collections: list[CollectionModel], faker: Faker) -> CollectionModel:
        return faker.random_element(collections)

    @pytest.fixture
    def collections(
            self, playlists: list[RemoteMutablePlaylist], tracks: list[Track], faker: Faker
    ) -> list[CollectionModel]:
        return [
            MockCollection(
                name=pl.name,
                cursor=MockUrlCursor(url=faker.url()),
                all_items=faker.random_elements(tracks),
                uri=SimpleURI.create_random(MockCollection.type),
            )
            for pl in playlists
        ]

    @pytest.fixture
    def mock_get_empty_playlist_items(self, tracks: list[RemoteTrack], faker: Faker) -> Generator[Mock, None, None]:
        with patch.object(
                PlaylistReadWriteEndpoints, "get_all", new_callable=AsyncMock
        ) as mock_get_all:
            yield mock_get_all

    @pytest.fixture
    def playlist_properties(self, model: Checker, faker: Faker) -> dict[str, Any]:
        properties = faker.pydict()
        properties.pop("name", None)  # name is not allowed as a key
        model.playlist_properties = properties
        return properties

    async def assert_create_playlist(
            self, model: Checker, collection: MockCollection, playlists: list[RemoteMutablePlaylist]
    ) -> RemoteMutablePlaylist:
        assert not model._playlists
        expected_playlist = next(pl for pl in playlists if pl.name.casefold() == collection.name.casefold())
        expected_items = list(collection.items)

        await model._setup_playlist(collection)

        assert list(expected_playlist.tracks) == expected_items

        assert model._collections == {expected_playlist.uri: collection}
        assert model._collections[expected_playlist.uri] is collection

        assert model._playlists == {expected_playlist.uri: expected_playlist}
        assert model._playlists[expected_playlist.uri] is expected_playlist
        assert model._playlists[expected_playlist.uri].tracks == expected_items

        assert model._playlists_initial == {expected_playlist.uri: expected_playlist}
        assert model._playlists_initial[expected_playlist.uri] is not expected_playlist
        assert model._playlists_initial[expected_playlist.uri].tracks != expected_items

        return expected_playlist

    ###########################################################################
    ## Tests
    ###########################################################################
    async def test_get_playlist(
            self,
            model: Checker,
            collection: MockCollection,
            playlists: list[RemoteMutablePlaylist],
            playlist_properties: dict[str, Any],
            mock_get_playlist: Mock,
            mock_create_playlist: Mock,
            mock_sync_playlist: Mock,
            mock_follow_playlist: Mock,
    ) -> None:
        model.use_existing_playlists = True

        playlist = await self.assert_create_playlist(model, playlists=playlists, collection=collection)

        mock_get_playlist.assert_called_once_with(name=collection.name, **playlist_properties)
        mock_create_playlist.assert_not_called()
        mock_sync_playlist.assert_called_once_with(api=model.api, kind="refresh", dry_run=False, show_bar=False)
        mock_follow_playlist.assert_called_once_with(playlist.uri.api_url)

    async def test_create_playlist(
            self,
            model: Checker,
            collection: MockCollection,
            playlists: list[RemoteMutablePlaylist],
            playlist_properties: dict[str, Any],
            mock_get_playlist: Mock,
            mock_create_playlist: Mock,
            mock_sync_playlist: Mock,
            mock_follow_playlist: Mock,
    ) -> None:
        model.use_existing_playlists = False

        playlist = await self.assert_create_playlist(model, playlists=playlists, collection=collection)

        mock_get_playlist.assert_not_called()
        mock_create_playlist.assert_called_once_with(name=collection.name, **playlist_properties)
        mock_sync_playlist.assert_called_once_with(api=model.api, kind="refresh", dry_run=False, show_bar=False)
        mock_follow_playlist.assert_called_once_with(playlist.uri.api_url)

    async def test_delete_playlist(
            self,
            model: Checker,
            playlist: RemoteMutablePlaylist,
            collection: CollectionModel,
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

        model._collections[playlist.uri] = collection
        model._playlists[playlist.uri] = playlist
        model._playlists_initial[playlist.uri] = playlist

        await model._teardown_playlist(playlist_cleared)

        mock_sync_playlist.assert_not_called()
        mock_remove_playlist.assert_called_once_with(playlist.uri.api_url, uris=expected_uris, show_bar=False)
        mock_delete_playlist.assert_called_once_with(playlist.uri.api_url)

        assert playlist.uri not in model._collections
        assert playlist.uri not in model._playlists
        assert playlist.uri not in model._playlists_initial

    async def test_restore_playlist(
            self,
            model: Checker,
            playlist: RemoteMutablePlaylist,
            collection: CollectionModel,
            tracks: list[RemoteTrack],
            mock_sync_playlist: Mock,
            mock_remove_playlist: Mock,
            mock_delete_playlist: Mock,
    ):
        playlist.tracks.extend(tracks)

        model._collections[playlist.uri] = collection
        model._playlists[playlist.uri] = playlist
        model._playlists_initial[playlist.uri] = playlist

        await model._teardown_playlist(playlist)

        mock_sync_playlist.assert_called_once_with(api=model.api, kind="refresh", dry_run=False, show_bar=False)
        mock_remove_playlist.assert_not_called()
        mock_delete_playlist.assert_not_called()

        assert playlist.uri not in model._collections
        assert playlist.uri not in model._playlists
        assert playlist.uri not in model._playlists_initial

    @pytest.fixture
    def mock_teardown_playlist(self, model: Checker, mocker: MockerFixture) -> Mock:
        return mocker.spy(model, "_teardown_playlist")

    async def test_teardown_playlists_skips(
            self,
            model: Checker,
            playlists: list[RemoteMutablePlaylist],
            mock_teardown_playlist: Mock,
    ):
        assert not model._collections
        assert not model._playlists
        assert not model._playlists_initial

        await model._teardown_playlists()

        assert not model._collections
        assert not model._playlists
        assert not model._playlists_initial

        mock_teardown_playlist.assert_not_called()

    async def test_teardown_playlists(
            self,
            model: Checker,
            playlists: list[RemoteMutablePlaylist],
            collections: list[CollectionModel],
            mock_teardown_playlist: Mock,
            faker: Faker,
    ):
        for pl in faker.random_elements(playlists):
            pl.tracks.clear()

        model._collections = {pl.uri: coll for pl, coll in zip(playlists, collections)}
        model._playlists = {pl.uri: pl for pl in playlists}
        model._playlists_initial = {pl.uri: pl for pl in playlists}

        await model._teardown_playlists()

        assert not model._collections
        assert not model._playlists
        assert not model._playlists_initial

        assert mock_teardown_playlist.call_count == len(playlists)
