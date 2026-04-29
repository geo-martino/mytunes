from asyncio import Semaphore
from collections import namedtuple
from collections.abc import Collection, Generator
from typing import ClassVar, get_args, Any
from unittest.mock import patch, AsyncMock, Mock

import pytest
from aiorequestful.response.exception import ResponseError
from faker import Faker
from pytest_mock import MockerFixture
from yarl import URL

from mytunes import MODULE_ROOT
from mytunes.core._collection._sync import SYNC_TYPE
from mytunes.core._collection.library import RemoteMutableLibrary
from mytunes.core._collection.library._remote._base import RemotePlaylistDump
from mytunes.core._collection.playlist import RemoteMutablePlaylist, RemotePlaylist
from mytunes.core._item.album import Album, RemoteAlbum
from mytunes.core._item.artist import Artist, RemoteArtist
from mytunes.core._item.track import RemoteTrack, Track
from mytunes.core.api import RemoteAPI, BatchWriteEndpoints, ItemReadEndpoints, BatchReadEndpoints
from mytunes.core.api.playlist import PlaylistLibraryEndpoints
from mytunes.core.properties.uri import URI
from tests.core._collection.library.remote.utils import MockRemoteLibrary
from tests.core._collection.utils import assert_sync_items_result
from tests.remote import SimpleURI
from tests.testers import BaseModelTester


class TestRemoteMutableLibrary(BaseModelTester):
    class MockRemoteMutableLibrary(RemoteMutableLibrary):
        source: ClassVar[str] = MockRemoteLibrary.source

    @pytest.fixture
    def model(self, api: RemoteAPI) -> RemoteMutableLibrary:
        return self.MockRemoteMutableLibrary(api=api)

    @pytest.fixture
    def mock_semaphore(self, mocker: MockerFixture) -> Mock:
        return mocker.spy(Semaphore, "acquire")

    ###########################################################################
    ## Add library items
    ###########################################################################
    @staticmethod
    def _return_length(uris: Collection, *_, **__) -> int:
        return len(uris)

    @pytest.fixture
    def mock_add_many(self) -> Generator[Mock]:
        with patch.object(
                BatchWriteEndpoints, "add_many", side_effect=self._return_length, new_callable=AsyncMock
        ) as mock_add:
            yield mock_add

    @pytest.fixture
    def mock_get_many(self) -> Generator[Mock]:
        with patch.object(BatchReadEndpoints, "get_many", new_callable=AsyncMock) as mock_get:
            yield mock_get

    async def test_add_library_items_from_resources(
            self,
            model: RemoteMutableLibrary,
            tracks: list[RemoteTrack],
            mock_add_many: Mock,
            mock_get_many: Mock,
    ):
        mock_get_many.return_value = tracks

        result = await model._add_library_items(items=tracks, items_type="tracks", api=model.api.tracks)
        assert result == tracks

    async def test_add_library_items_from_uris(
            self,
            model: RemoteMutableLibrary,
            tracks: list[RemoteTrack],
            mock_add_many: Mock,
            mock_get_many: Mock,
    ):
        mock_get_many.return_value = tracks
        uris = [track.uri for track in tracks]

        result = await model._add_library_items(items=uris, items_type="tracks", api=model.api.tracks)
        assert result == tracks

    async def test_add_tracks(
            self,
            model: RemoteMutableLibrary,
            tracks: list[RemoteTrack],
            mock_add_many: Mock,
            mock_get_many: Mock,
    ):
        mock_get_many.return_value = tracks

        model.tracks.clear()
        uris = [track.uri for track in tracks]

        await model.add_tracks(uris)
        assert model.tracks == tracks

    async def test_add_artists(
            self,
            model: RemoteMutableLibrary,
            artists: list[RemoteArtist],
            mock_add_many: Mock,
            mock_get_many: Mock,
    ):
        mock_get_many.return_value = artists

        model.tracks.clear()
        uris = [artist.uri for artist in artists]

        await model.add_artists(uris)
        assert model.artists == artists

    async def test_add_albums(
            self,
            model: RemoteMutableLibrary,
            albums: list[RemoteAlbum],
            mock_add_many: Mock,
            mock_get_many: Mock,
    ):
        mock_get_many.return_value = albums

        model.tracks.clear()
        uris = [album.uri for album in albums]

        await model.add_albums(uris)
        assert model.albums == albums

    ###########################################################################
    ## Sync library items
    ###########################################################################
    @pytest.fixture
    def mock_filter_items(self, model: RemoteMutableLibrary, mocker: MockerFixture) -> Mock:
        return mocker.spy(model, "_filter_items")

    @pytest.fixture(autouse=True)
    def mock_get_sync_items(self, tracks: list[RemoteTrack], faker: Faker) -> Generator[Mock]:
        initial = [track.uri for track in tracks]
        add = faker.random_elements(initial, unique=True)
        remove = faker.random_elements(initial, length=faker.random_int(0, len(add)), unique=True)
        unchanged = faker.random_elements(initial, unique=True)

        target = f"{MODULE_ROOT}.core._collection.library._remote._mutable.get_sync_items"
        with patch(target, return_value=(add, remove, unchanged)) as mock_get_items:
            yield mock_get_items

    @pytest.fixture
    def mock_remove_many(self) -> Generator[Mock]:
        with patch.object(
                BatchWriteEndpoints, "remove_many", side_effect=self._return_length, new_callable=AsyncMock
        ) as mock_remove:
            yield mock_remove

    @pytest.fixture
    def mock_get_all(self, mock_get_all: Mock, faker: Faker) -> list[URI]:
        uris = [SimpleURI.from_id(i, kind=RemoteTrack.type) for i in range(faker.random_int(1, 10))]
        mock_get_all.return_value = uris
        return mock_get_all

    async def test_sync_library_items(
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

        result = await model._sync_library_items(
            kind=kind, items_type="tracks", items=tracks, api=model.api.tracks, dry_run=False
        )

        mock_filter_items.assert_called_once_with(tracks, items_type="tracks")
        mock_get_all.assert_called_once()
        mock_get_sync_items.assert_called_once_with(kind, initial=initial, remote=remote)
        assert_sync_items_result(result, remote, add, remove, unchanged)

        mock_add_many.assert_called_once_with(add)
        mock_remove_many.assert_called_once_with(remove)

    async def test_sync_library_items_dry_run(
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

        result = await model._sync_library_items(
            kind=kind, items_type="tracks", items=tracks, api=model.api.tracks, dry_run=True
        )

        mock_filter_items.assert_called_once_with(tracks, items_type="tracks")
        mock_get_all.assert_called_once()
        mock_get_sync_items.assert_called_once_with(kind, initial=initial, remote=remote)
        assert_sync_items_result(result, remote, add, remove, unchanged)

        mock_add_many.assert_not_called()
        mock_remove_many.assert_not_called()

    @pytest.fixture
    def mock_sync_library_items(self, model: RemoteMutableLibrary) -> Generator[Mock]:
        with patch.object(model, "_sync_library_items") as mock_sync:
            yield mock_sync

    async def test_sync_tracks(self, model: RemoteMutableLibrary, mock_sync_library_items: Mock, faker: Faker):
        kind = faker.random_element(get_args(SYNC_TYPE))
        dry_run = faker.boolean()

        await model.sync_tracks(kind=kind, dry_run=dry_run)
        mock_sync_library_items.assert_called_once_with(
            kind=kind, items_type="tracks", items=model.tracks, api=model.api.tracks, dry_run=dry_run
        )

    async def test_sync_artists(self, model: RemoteMutableLibrary, mock_sync_library_items: Mock, faker: Faker):
        kind = faker.random_element(get_args(SYNC_TYPE))
        dry_run = faker.boolean()

        await model.sync_artists(kind=kind, dry_run=dry_run)
        mock_sync_library_items.assert_called_once_with(
            kind=kind, items_type="artists", items=model.artists, api=model.api.artists, dry_run=dry_run
        )

    async def test_sync_albums(self, model: RemoteMutableLibrary, mock_sync_library_items: Mock, faker: Faker):
        kind = faker.random_element(get_args(SYNC_TYPE))
        dry_run = faker.boolean()

        await model.sync_albums(kind=kind, dry_run=dry_run)
        mock_sync_library_items.assert_called_once_with(
            kind=kind, items_type="albums", items=model.albums, api=model.api.albums, dry_run=dry_run
        )

    ###########################################################################
    ## Create/sync playlists
    ###########################################################################
    @pytest.fixture
    def mock_create_playlist(
            self, model: RemoteMutableLibrary, playlists: list[RemotePlaylist]
    ) -> Generator[Mock]:
        def _get_playlist(name: str, *_, **__) -> RemotePlaylist:
            return next(pl for pl in playlists if str(pl.name) == name)

        with patch.object(
            PlaylistLibraryEndpoints, "create", side_effect=_get_playlist, new_callable=AsyncMock
        ) as mock_create:
            yield mock_create

    @pytest.fixture
    def mock_get_or_create_playlist(
            self, model: RemoteMutableLibrary, playlists: list[RemotePlaylist]
    ) -> Generator[Mock]:
        def _get_playlist(name: str, *_, **__) -> RemotePlaylist:
            return next(pl for pl in playlists if str(pl.name) == name)

        with patch.object(
            PlaylistLibraryEndpoints, "get_or_create", side_effect=_get_playlist, new_callable=AsyncMock
        ) as mock_get_or_create:
            yield mock_get_or_create

    async def test_create_playlist(
            self,
            model: RemoteMutableLibrary,
            playlists: list[RemoteMutablePlaylist],
            mock_create_playlist: Mock,
            faker: Faker
    ):
        model.playlists.replace(playlists)
        expected = faker.random_element(playlists)
        model.playlists.remove(expected)
        assert expected not in model.playlists

        name = expected.name
        description = expected.description
        public = expected.public

        playlist = await model.create_playlist(name=name, description=description, public=public)
        mock_create_playlist.assert_called_once_with(name=name, description=description, public=public)

        assert playlist is expected
        assert playlist in model.playlists

    @pytest.fixture
    def mock_sync_properties(self, model: RemoteMutableLibrary) -> Generator[Mock]:
        with patch.object(RemoteMutablePlaylist, "sync_properties", new_callable=AsyncMock) as mock_sync_props:
            yield mock_sync_props

    @pytest.fixture
    def mock_sync_items(self, model: RemoteMutableLibrary) -> Generator[Mock]:
        with patch.object(RemoteMutablePlaylist, "sync_items", new_callable=AsyncMock) as mock_sync_items:
            yield mock_sync_items

    async def test_sync_playlists(
            self,
            model: RemoteMutableLibrary,
            playlists: list[RemoteMutablePlaylist],
            mock_get_or_create_playlist: Mock,
            mock_sync_properties: Mock,
            mock_sync_items: Mock,
            mock_semaphore: Mock,
            faker: Faker,
    ):
        model.playlists.extend(playlists)

        results = await model.sync_playlists()
        assert len(results) == len(playlists)

        assert mock_get_or_create_playlist.call_count == len(playlists)
        assert mock_sync_properties.call_count == len(playlists)
        assert mock_sync_items.call_count == len(playlists)
        assert mock_semaphore.call_count == len(playlists)

    ###########################################################################
    ## Restore library items
    ###########################################################################
    def test_extract_uris_from_backup(
            self,
            model: RemoteMutableLibrary,
            tracks: list[RemoteTrack],
            artists: list[RemoteArtist],
            albums: list[RemoteAlbum],
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
            mock_sync_library_items: Mock,
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
        mock_sync_library_items.assert_called_once_with(
            kind="refresh", items_type="tracks", items=tracks, api=model.api.tracks, dry_run=dry_run
        )

    async def test_restore_artists(
            self,
            model: RemoteMutableLibrary,
            artists: list[Artist],
            mock_get_many: Mock,
            mock_sync_library_items: Mock,
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
        mock_sync_library_items.assert_called_once_with(
            kind="refresh", items_type="artists", items=artists, api=model.api.artists, dry_run=dry_run
        )

    async def test_restore_albums(
            self,
            model: RemoteMutableLibrary,
            albums: list[Album],
            mock_get_many: Mock,
            mock_sync_library_items: Mock,
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
        mock_sync_library_items.assert_called_once_with(
            kind="refresh", items_type="albums", items=albums, api=model.api.albums,  dry_run=dry_run
        )

    ###########################################################################
    ## Restore playlists
    ###########################################################################
    def test_extract_playlists_from_backup(
            self,
            model: RemoteMutableLibrary,
            playlists: list[RemotePlaylist],
            faker: Faker
    ):
        dump = {
            faker.uuid4(): {
                "name": faker.name(), "uri": pl.uri, "items": [{"uri": tr.uri} for tr in pl.tracks]
            }
            for pl in playlists
        }
        expected = tuple(dump.values())

        assert model._extract_playlists_from_backup(dump) == expected
        assert model._extract_playlists_from_backup({"playlists": dump}) == expected
        assert model._extract_playlists_from_backup(dump.values()) == expected
        assert model._extract_playlists_from_backup({"playlists": dump.values()}) == expected

    @pytest.fixture
    def playlists_dump(self, playlists: list[RemotePlaylist]) -> list[RemotePlaylistDump]:
        return [
            RemotePlaylistDump(name=pl.name, uri=pl.uri, items=[str(tr.uri) for tr in pl.tracks])
            for pl in playlists
        ]

    @pytest.fixture
    def mock_get_playlist(
            self, model: RemoteMutableLibrary, playlists: list[RemotePlaylist], faker: Faker
    ) -> Generator[tuple[Mock, list[URI]]]:
        failed: list[URI] = []
        response = namedtuple("ClientResponse", ["status"])

        def _get_playlist_or_raise_error(uri: URI, *_, **__) -> RemotePlaylist:
            playlist = next(pl for pl in playlists if str(pl.uri) == str(uri))
            if faker.boolean():  # randomly decide whether the playlist 'exists' or not
                return playlist

            failed.append(uri)
            # noinspection PyTypeChecker
            raise ResponseError(response=response(status=404))

        with patch.object(
                ItemReadEndpoints, "get", side_effect=_get_playlist_or_raise_error, new_callable=AsyncMock
        ) as mock_get:
            yield mock_get, failed
            assert mock_get.call_count == len(playlists)

    async def test_restore_playlists_dry_run(
            self,
            model: RemoteMutableLibrary,
            playlists: list[RemotePlaylist],
            playlists_dump: list[dict[str, Any]],
            mock_get_playlist: tuple[Mock, list[URI]],
            mock_create_playlist: Mock,
            mock_get_many: Mock,
            mock_sync_items: Mock,
            mock_semaphore: Mock,
    ):
        result = await model.restore_playlists(playlists_dump, dry_run=True)

        assert len(result) == len(playlists)

        mock_get_playlist, failed = mock_get_playlist

        mock_create_playlist.assert_not_called()
        assert mock_get_many.call_count == len(playlists) - len(failed)
        assert mock_sync_items.call_count == len(playlists) - len(failed)
        assert mock_semaphore.call_count == len(playlists)

    async def test_restore_playlists(
            self,
            model: RemoteMutableLibrary,
            playlists: list[RemotePlaylist],
            playlists_dump: list[dict[str, Any]],
            mock_get_playlist: tuple[Mock, list[URI]],
            mock_create_playlist: Mock,
            mock_get_many: Mock,
            mock_sync_items: Mock,
            mock_semaphore: Mock,
    ):
        result = await model.restore_playlists(playlists_dump, dry_run=False)

        assert len(result) == len(playlists)

        mock_get_playlist, failed = mock_get_playlist

        assert mock_create_playlist.call_count == len(failed)
        assert mock_get_many.call_count == len(playlists)
        assert mock_sync_items.call_count == len(playlists)
        assert mock_semaphore.call_count == len(playlists)
