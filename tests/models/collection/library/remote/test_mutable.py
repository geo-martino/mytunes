from collections import namedtuple
from collections.abc import Collection
from typing import ClassVar, get_args, Generator, Any
from unittest.mock import patch, AsyncMock, Mock

import pytest
from aiorequestful.response.exception import ResponseError
from faker import Faker
from pytest_mock import MockerFixture

from musify import MODULE_ROOT
from musify.models.api import RemoteAPI, WriteSavedEndpoints, ReadItemEndpoints, ReadItemsEndpoints
from musify.models.api.playlist import PlaylistReadWriteSavedEndpoints
from musify.models.collection._sync import SYNC_TYPE
from musify.models.collection.library import RemoteMutableLibrary
from musify.models.collection.playlist import RemoteMutablePlaylist, Playlist, RemotePlaylist
from musify.models.item.album import Album, RemoteAlbum
from musify.models.item.artist import Artist, RemoteArtist
from musify.models.item.track import RemoteTrack, Track
from musify.models.properties.uri import URI
from tests.models.api.utils import MockRemoteAPI
from tests.models.collection.library.remote.utils import MockRemoteLibrary
from tests.models.collection.utils import assert_sync_items_result
from tests.models.testers import BaseModelTester
from tests.processors_new.check import conftest
from tests.utils import SimpleURI


class TestRemoteMutableLibrary(BaseModelTester):
    class MockRemoteMutableLibrary(RemoteMutableLibrary):
        source: ClassVar[str] = MockRemoteLibrary.source

    @pytest.fixture
    def api(self) -> RemoteAPI:
        return MockRemoteAPI()

    @pytest.fixture
    def model(self, api: RemoteAPI) -> RemoteMutableLibrary:
        return self.MockRemoteMutableLibrary(api=api)

    ###########################################################################
    ## Create/sync playlists
    ###########################################################################
    @pytest.fixture
    def mock_create_playlist(
            self, model: RemoteMutableLibrary, playlists: list[RemotePlaylist]
    ) -> Generator[Mock, None, None]:
        def _get_playlist(name: str, *_, **__) -> RemotePlaylist:
            return next(pl for pl in playlists if str(pl.name) == name)

        with patch.object(
            PlaylistReadWriteSavedEndpoints, "create", side_effect=_get_playlist, new_callable=AsyncMock
        ) as mock_create:
            yield mock_create

    @pytest.fixture
    def mock_get_or_create_playlist(
            self, model: RemoteMutableLibrary, playlists: list[RemotePlaylist]
    ) -> Generator[Mock, None, None]:
        def _get_playlist(name: str, *_, **__) -> RemotePlaylist:
            return next(pl for pl in playlists if str(pl.name) == name)

        with patch.object(
            PlaylistReadWriteSavedEndpoints, "get_or_create", side_effect=_get_playlist, new_callable=AsyncMock
        ) as mock_get_or_create:
            yield mock_get_or_create

    async def test_create_playlist(
            self,
            model: RemoteMutableLibrary,
            playlists: list[RemoteMutablePlaylist],
            mock_create_playlist: Mock,
            faker: Faker
    ):
        expected = faker.random_element(playlists)
        model.playlists.remove(expected)
        assert expected.name not in model.playlists

        name = expected.name
        description = expected.description
        public = expected.public

        playlist = await model.create_playlist(name=name, description=description, public=public)
        mock_create_playlist.assert_called_once_with(name=name, description=description, public=public)

        assert playlist is expected
        assert playlist.name in model.playlists

    @pytest.fixture
    def mock_sync_items(
            self, model: RemoteMutableLibrary, playlists: list[RemotePlaylist]
    ) -> Generator[Mock, None, None]:
        with patch.object(RemoteMutablePlaylist, "sync_items", new_callable=AsyncMock) as mock_sync_items:
            yield mock_sync_items

    async def test_sync_playlists(
            self,
            model: RemoteMutableLibrary,
            playlists: list[RemoteMutablePlaylist],
            mock_get_or_create_playlist: Mock,
            mock_sync_items: Mock,
            faker: Faker,
    ):
        playlists = {pl.name: pl for pl in playlists}
        model.playlists.update(playlists, extract_keys=False)

        results = await model.sync_playlist_items()
        assert len(results) == len(playlists)

        assert mock_get_or_create_playlist.call_count == len(playlists)
        assert mock_sync_items.call_count == len(playlists)

    ###########################################################################
    ## Sync saved items
    ###########################################################################
    @pytest.fixture
    def mock_filter_items(self, model: RemoteMutableLibrary, mocker: MockerFixture) -> Mock:
        return mocker.spy(model, "_filter_items")

    @pytest.fixture(autouse=True)
    def mock_get_sync_items(self, tracks: list[RemoteTrack], faker: Faker) -> Generator[Mock, None, None]:
        initial = [track.uri for track in tracks]
        add = faker.random_elements(initial)
        remove = faker.random_elements(initial, length=faker.random_int(0, len(add)))
        unchanged = faker.random_elements(initial)

        target = f"{MODULE_ROOT}.models.collection.library._remote._mutable.get_sync_items"
        with patch(target, return_value=(add, remove, unchanged)) as mock_get_items:
            yield mock_get_items

    @staticmethod
    def _return_length(uris: Collection, *_, **__) -> int:
        return len(uris)

    @pytest.fixture
    def mock_add_many(self) -> Generator[Mock, None, None]:
        with patch.object(
                WriteSavedEndpoints, "add_many", side_effect=self._return_length, new_callable=AsyncMock
        ) as mock_add:
            yield mock_add

    @pytest.fixture
    def mock_remove_many(self) -> Generator[Mock, None, None]:
        with patch.object(
                WriteSavedEndpoints, "remove_many", side_effect=self._return_length, new_callable=AsyncMock
        ) as mock_remove:
            yield mock_remove

    @pytest.fixture
    def mock_get_all(self, mock_get_all: Mock, faker: Faker) -> list[URI]:
        uris = [SimpleURI.from_id(i, kind=RemoteTrack.type) for i in range(faker.random_int(1, 10))]
        mock_get_all.return_value = uris
        return mock_get_all

    async def test_sync_saved_items(
            self,
            model: RemoteMutableLibrary,
            tracks: list[RemoteTrack],
            mock_filter_items: Mock,
            mock_get_all: Mock,
            mock_get_sync_items: Mock,
            mock_add_many: Mock,
            mock_remove_many: Mock,
            faker: Faker,
    ):
        kind = faker.random_element(get_args(SYNC_TYPE))

        initial = [track.uri for track in tracks]
        add, remove, unchanged = mock_get_sync_items.return_value
        remote = mock_get_all.return_value

        result = await model._sync_saved_items(
            kind=kind, items_type="tracks", items=tracks, api=conftest.tracks, dry_run=False
        )

        mock_filter_items.assert_called_once_with(tracks, items_type="tracks")
        mock_get_all.assert_called_once()
        mock_get_sync_items.assert_called_once_with(kind, initial=initial, remote=remote)
        assert_sync_items_result(result, remote, add, remove, unchanged)

        mock_add_many.assert_called_once_with(add)
        mock_remove_many.assert_called_once_with(remove)

    async def test_sync_saved_items_dry_run(
            self,
            model: RemoteMutableLibrary,
            tracks: list[RemoteTrack],
            mock_filter_items: Mock,
            mock_get_all: Mock,
            mock_get_sync_items: Mock,
            mock_add_many: Mock,
            mock_remove_many: Mock,
            faker: Faker,
    ):
        kind = faker.random_element(get_args(SYNC_TYPE))

        initial = [track.uri for track in tracks]
        add, remove, unchanged = mock_get_sync_items.return_value
        remote = mock_get_all.return_value

        result = await model._sync_saved_items(
            kind=kind, items_type="tracks", items=tracks, api=conftest.tracks, dry_run=True
        )

        mock_filter_items.assert_called_once_with(tracks, items_type="tracks")
        mock_get_all.assert_called_once()
        mock_get_sync_items.assert_called_once_with(kind, initial=initial, remote=remote)
        assert_sync_items_result(result, remote, add, remove, unchanged)

        mock_add_many.assert_not_called()
        mock_remove_many.assert_not_called()

    @pytest.fixture
    def mock_sync_saved_items(self, model: RemoteMutableLibrary) -> Generator[Mock, None, None]:
        with patch.object(model, "_sync_saved_items") as mock_sync:
            yield mock_sync

    async def test_sync_tracks(self, model: RemoteMutableLibrary, mock_sync_saved_items: Mock, faker: Faker):
        kind = faker.random_element(get_args(SYNC_TYPE))
        dry_run = faker.boolean()

        await model.sync_tracks(kind=kind, dry_run=dry_run)
        mock_sync_saved_items.assert_called_once_with(
            kind=kind, items_type="tracks", items=model.tracks, api=conftest.tracks, dry_run=dry_run
        )

    async def test_sync_artists(self, model: RemoteMutableLibrary, mock_sync_saved_items: Mock, faker: Faker):
        kind = faker.random_element(get_args(SYNC_TYPE))
        dry_run = faker.boolean()

        await model.sync_artists(kind=kind, dry_run=dry_run)
        mock_sync_saved_items.assert_called_once_with(
            kind=kind, items_type="artists", items=model.artists, api=model.api.artists, dry_run=dry_run
        )

    async def test_sync_albums(self, model: RemoteMutableLibrary, mock_sync_saved_items: Mock, faker: Faker):
        kind = faker.random_element(get_args(SYNC_TYPE))
        dry_run = faker.boolean()

        await model.sync_albums(kind=kind, dry_run=dry_run)
        mock_sync_saved_items.assert_called_once_with(
            kind=kind, items_type="albums", items=model.albums, api=model.api.albums, dry_run=dry_run
        )

    ###########################################################################
    ## Restore playlists
    ###########################################################################
    def test_extract_playlists_from_backup(
            self,
            model: RemoteMutableLibrary,
            playlists: list[Playlist],
            faker: Faker
    ):
        dump = {faker.uuid4(): {"uri": pl.uri, "tracks": [{"uri": tr.uri} for tr in pl.tracks]} for pl in playlists}
        expected = tuple((pl["uri"], pl, tuple(tr["uri"] for tr in pl["tracks"])) for pl in dump.values())

        assert model._extract_playlists_from_backup(dump) == expected
        assert model._extract_playlists_from_backup({"playlists": dump}) == expected
        assert model._extract_playlists_from_backup(dump.values()) == expected
        assert model._extract_playlists_from_backup({"playlists": dump.values()}) == expected

    @pytest.fixture
    def playlists_dump(self, playlists: list[Playlist]) -> list[dict[str, Any]]:
        return [
            {"name": pl.name, "uri": pl.uri, "tracks": [{"uri": str(tr.uri) for tr in pl.tracks}]}
            for pl in playlists
        ]

    @pytest.fixture
    def mock_get_playlist(
            self, model: RemoteMutableLibrary, playlists: list[RemotePlaylist], faker: Faker
    ) -> Generator[tuple[Mock, list[str]], None, None]:
        failed: list[str] = []
        response = namedtuple("ClientResponse", ["status"])

        def _get_playlist_or_raise_error(uri: str, *_, **__) -> RemotePlaylist:
            playlist = next(pl for pl in playlists if str(pl.uri) == uri)
            if faker.boolean():  # randomly decide whether the playlist 'exists' or not
                return playlist

            failed.append(uri)
            # noinspection PyTypeChecker
            raise ResponseError(response=response(status=404))

        with patch.object(
                ReadItemEndpoints, "get", side_effect=_get_playlist_or_raise_error, new_callable=AsyncMock
        ) as mock_get:
            yield mock_get, failed
            assert mock_get.call_count == len(playlists)

    @pytest.fixture
    def mock_get_many(self) -> Generator[Mock, None, None]:
        with patch.object(ReadItemsEndpoints, "get_many", new_callable=AsyncMock) as mock_get:
            yield mock_get

    async def test_restore_playlists_dry_run(
            self,
            model: RemoteMutableLibrary,
            playlists: list[RemotePlaylist],
            playlists_dump: list[dict[str, Any]],
            mock_get_playlist: tuple[Mock, list[str]],
            mock_create_playlist: Mock,
            mock_get_many: Mock,
            mock_sync_items: Mock,
    ):
        result = await model.restore_playlists(playlists_dump, dry_run=True)
        assert len(result) == len(playlists)

        mock_get_playlist, failed = mock_get_playlist

        mock_create_playlist.assert_not_called()
        assert mock_get_many.call_count == len(playlists) - len(failed)
        assert mock_sync_items.call_count == len(playlists) - len(failed)

    async def test_restore_playlists(
            self,
            model: RemoteMutableLibrary,
            playlists: list[RemotePlaylist],
            playlists_dump: list[dict[str, Any]],
            mock_get_playlist: tuple[Mock, list[str]],
            mock_create_playlist: Mock,
            mock_get_many: Mock,
            mock_sync_items: Mock,
    ):
        result = await model.restore_playlists(playlists_dump, dry_run=False)
        assert len(result) == len(playlists)

        mock_get_playlist, failed = mock_get_playlist

        assert mock_create_playlist.call_count == len(failed)
        assert mock_get_many.call_count == len(playlists)
        assert mock_sync_items.call_count == len(playlists)

    ###########################################################################
    ## Restore saved items
    ###########################################################################
    def test_extract_uris_from_backup(
            self,
            model: RemoteMutableLibrary,
            tracks: list[Track],
            artists: list[Artist],
            albums: list[Album],
            faker: Faker
    ):
        dump = {track.uri: {} for track in tracks}
        expected = tuple(track.uri for track in tracks)
        assert model._extract_uris_from_backup(expected, key="tracks") == expected
        assert model._extract_uris_from_backup(dump, key="tracks") == expected
        assert model._extract_uris_from_backup({"tracks": dump}, key="tracks") == expected

        dump = {faker.uuid4(): {"uri": artist.uri} for artist in artists}
        expected = tuple(artist.uri for artist in artists)
        assert model._extract_uris_from_backup(expected, key="artists") == expected
        assert model._extract_uris_from_backup(dump, key="artists") == expected
        assert model._extract_uris_from_backup({"artists": dump}, key="artists") == expected

        dump = [{"uri": album.uri} for album in albums]
        expected = tuple(album.uri for album in albums)
        assert model._extract_uris_from_backup(expected, key="albums") == expected
        assert model._extract_uris_from_backup(dump, key="albums") == expected
        assert model._extract_uris_from_backup({"albums": dump}, key="albums") == expected

    async def test_restore_tracks(
            self,
            model: RemoteMutableLibrary,
            tracks: list[Track],
            mock_get_many: Mock,
            mock_sync_saved_items: Mock,
            faker: Faker,
    ):
        dry_run = faker.boolean()

        uris = tuple(
            SimpleURI.create_random(RemoteTrack.type)
            for _ in range(faker.random_int(1, 10))
        )

        mock_get_many.return_value = tracks

        assert model.tracks != tracks

        await model.restore_tracks(uris, dry_run=dry_run)
        assert model.tracks == tracks

        mock_get_many.assert_called_once_with(uris)
        mock_sync_saved_items.assert_called_once_with(
            kind="refresh", items_type="tracks", items=tracks, api=conftest.tracks, dry_run=dry_run
        )

    async def test_restore_artists(
            self,
            model: RemoteMutableLibrary,
            artists: list[Artist],
            mock_get_many: Mock,
            mock_sync_saved_items: Mock,
            faker: Faker,
    ):
        dry_run = faker.boolean()

        uris = tuple(
            SimpleURI.create_random(RemoteArtist.type)
            for _ in range(faker.random_int(1, 10))
        )

        mock_get_many.return_value = artists

        assert model.artists != artists

        await model.restore_artists(uris, dry_run=dry_run)
        assert model.artists == artists

        mock_get_many.assert_called_once_with(uris)
        mock_sync_saved_items.assert_called_once_with(
            kind="refresh", items_type="artists", items=artists, api=model.api.artists, dry_run=dry_run
        )

    async def test_restore_albums(
            self,
            model: RemoteMutableLibrary,
            albums: list[Album],
            mock_get_many: Mock,
            mock_sync_saved_items: Mock,
            faker: Faker,
    ):
        dry_run = faker.boolean()

        uris = tuple(
            SimpleURI.create_random(RemoteAlbum.type)
            for _ in range(faker.random_int(1, 10))
        )

        mock_get_many.return_value = albums

        assert model.albums != albums

        await model.restore_albums(uris, dry_run=dry_run)
        assert model.albums == albums

        mock_get_many.assert_called_once_with(uris)
        mock_sync_saved_items.assert_called_once_with(
            kind="refresh", items_type="albums", items=albums, api=model.api.albums,  dry_run=dry_run
        )
