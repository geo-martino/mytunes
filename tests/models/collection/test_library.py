from collections import namedtuple
from collections.abc import Collection
from typing import ClassVar, Generator, get_args, NamedTuple, Any
from unittest.mock import patch, Mock, AsyncMock

import pytest
from aiohttp import ClientResponseError, ClientResponse
from aiorequestful.request import RequestHandler
from aiorequestful.response.exception import ResponseError
from faker import Faker

from musify.models.api import RemoteAPI, ReadSavedEndpoints, WriteCollectionEndpoints, WriteSavedEndpoints, \
    ReadItemsEndpoints, ReadItemEndpoints
from musify.models.api.playlist import PlaylistReadWriteSavedEndpoints
# noinspection PyProtectedMember
from musify.models.collection._sync import SYNC_TYPE
from musify.models.collection.library import HasTracksAndPlaylists, RemoteLibrary, RemoteMutableLibrary
from musify.models.collection.playlist import Playlist, RemotePlaylist, RemoteMutablePlaylist
from musify.models.item.album import Album, RemoteAlbum
from musify.models.item.artist import Artist, RemoteArtist
from musify.models.item.track import Track, RemoteTrack
from musify.models.properties.uri import URI
from musify.models.remote import RemoteResource
from musify.models.user import RemoteUser
from tests.models.api.utils import MockRemoteAPI, MockUrlCursor
from tests.models.collection.utils import assert_sync_items_result
from tests.models.testers import BaseResourceTester, BaseModelTester
from tests.utils import SimpleURI


class TestLibrary(BaseResourceTester):
    @pytest.fixture
    def model(self, faker: Faker) -> HasTracksAndPlaylists:
        return HasTracksAndPlaylists()

    def test_tracks_in_playlists(self, tracks: list[Track], playlists: list[Playlist], faker: Faker):
        for pl in playlists:
            pl.tracks[:] = faker.random_elements(tracks)

        tracks = faker.random_elements(tracks)
        library = HasTracksAndPlaylists(tracks=tracks, playlists=playlists)
        assert all(track not in library.tracks for track in library.tracks_in_playlists)

        uris = [str(track.uri) for track in library.tracks_in_playlists]
        assert sorted(uris) == sorted(set(uris))  # no duplicates

    def test_items_count(self, tracks: list[Track], playlists: list[Playlist]):
        library = HasTracksAndPlaylists(tracks=tracks, playlists=playlists)
        assert library.count == len(tracks)

    def test_dump(self, model: HasTracksAndPlaylists, playlists: list[Playlist], tracks: list[Track]):
        model = model.__class__(playlists=playlists, tracks=tracks)

        backup = model.dump()
        assert len(backup["playlists"]) == len(model.playlists)
        for pl_id, pl_backup in backup["playlists"].items():
            pl = model.playlists[pl_backup["uri"]]

            assert isinstance(pl_backup, dict)

            assert "name" in pl_backup and isinstance(pl_backup["name"], str)
            assert pl_backup["name"] == pl.name

            assert "tracks" in pl_backup and len(pl_backup["tracks"]) == len(pl.tracks)
            assert all(isinstance(track, dict) for track in pl_backup["tracks"])

            assert "uri" in pl_backup and isinstance(pl_backup["uri"], str)
            assert pl_backup["uri"] == pl.uri

        for track, track_backup in zip(tracks, backup["tracks"]):
            assert isinstance(track_backup, dict)

            assert "name" in track_backup and isinstance(track_backup["name"], str)
            assert track_backup["name"] == track.name

            assert "uri" in track_backup and isinstance(track_backup["uri"], str)
            assert track_backup["uri"] == track.uri


class MockRemoteLibrary(RemoteLibrary):
    source: ClassVar[str] = "test"


@pytest.fixture
def playlists(
        playlists: list[Playlist], tracks: list[Track], faker: Faker
) -> list[RemotePlaylist]:
    return [
        RemoteMutablePlaylist(
            **pl.model_dump(exclude={"tracks", "uri"}),
            owner=RemoteUser(name=faker.name(), uri=SimpleURI.from_id(faker.pystr(22, 22), kind=RemoteUser.type)),
            cursor=MockUrlCursor(url=faker.url()),
            tracks=faker.random_elements(tracks),
            uri=SimpleURI.from_id(faker.pystr(22, 22), kind=RemotePlaylist.type)
        )
        for pl in playlists
    ]


@pytest.fixture
def tracks(tracks: list[Track], faker: Faker) -> list[RemoteTrack]:
    return [
        RemoteTrack(
            **track.model_dump(exclude={"uri"}),
            uri=SimpleURI.from_id(faker.pystr(22, 22), kind=RemoteTrack.type)
        )
        for track in tracks
    ]


@pytest.fixture
def artists(artists: list[Artist], faker: Faker) -> list[RemoteArtist]:
    return [
        RemoteArtist(
            **artist.model_dump(exclude={"uri"}),
            uri=SimpleURI.from_id(faker.pystr(22, 22), kind=RemoteArtist.type)
        )
        for artist in artists
    ]


@pytest.fixture
def albums(albums: list[Album], faker: Faker) -> list[RemoteAlbum]:
    return [
        RemoteAlbum(
            **album.model_dump(exclude={"uri"}),
            uri=SimpleURI.from_id(faker.pystr(22, 22), kind=RemoteAlbum.type)
        )
        for album in albums
    ]


class TestRemoteLibrary(BaseModelTester):

    @pytest.fixture
    def api(self) -> RemoteAPI:
        return MockRemoteAPI()

    @pytest.fixture
    def model(self, api: RemoteAPI, user: RemoteUser) -> RemoteLibrary:
        library = MockRemoteLibrary(api=api)
        library._user = user
        return library

    @pytest.fixture
    def mock_get_all(self) -> Generator[Mock, None, None]:
        with patch.object(ReadSavedEndpoints, "get_all") as mock_get_all:
            yield mock_get_all

    @staticmethod
    def assert_items_loaded(loaded_items: Collection[RemoteResource], mock_get_all: Mock) -> None:
        """Assert that the given tracks were loaded into the model"""
        mock_get_all.assert_called_once()
        assert len(loaded_items) == len(mock_get_all.return_value)

        expected_uris = sorted(str(item.uri) for item in mock_get_all.return_value)
        assert sorted(str(item.uri) for item in loaded_items) == expected_uris

    async def test_load_playlists(self, model: RemoteLibrary, playlists: list[Playlist], user: RemoteUser, mock_get_all: Mock):
        for pl in playlists:
            pl.owner = user

        mock_get_all.return_value = playlists
        assert await model.load_playlists()
        self.assert_items_loaded(model.playlists.values(), mock_get_all)

        assert len(model.log_playlists(skip_log=True)) == len(playlists)

    async def test_load_saved_tracks(self, model: RemoteLibrary, tracks: list[Track], mock_get_all: Mock):
        mock_get_all.return_value = tracks
        assert await model.load_tracks()
        self.assert_items_loaded(model.tracks, mock_get_all)

        assert model.log_tracks(skip_log=True)

    async def test_load_saved_artists(self, model: RemoteLibrary, artists: list[Artist], mock_get_all: Mock):
        mock_get_all.return_value = artists
        assert await model.load_saved_artists()
        self.assert_items_loaded(model.artists, mock_get_all)

        assert model.log_artists(skip_log=True)

    async def test_load_saved_albums(self, model: RemoteLibrary, albums: list[Album], mock_get_all: Mock):
        mock_get_all.return_value = albums
        assert await model.load_saved_albums()
        self.assert_items_loaded(model.albums, mock_get_all)

        assert model.log_albums(skip_log=True)


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
    async def test_create_playlist(
            self, model: RemoteMutableLibrary, playlists: list[RemoteMutablePlaylist], faker: Faker
    ):
        name = faker.sentence()
        description = faker.text()
        public = faker.pybool()

        expected = faker.random_element(playlists)

        with patch.object(PlaylistReadWriteSavedEndpoints, "create", return_value=expected) as mock_create:
            playlist = await model.create_playlist(name=name, description=description, public=public)
            mock_create.assert_called_once_with(name=name, description=description, public=public)

            assert playlist is expected
            assert playlist.name in model.playlists

    async def test_sync_playlists(self, model: RemoteMutableLibrary, playlists: list[RemoteMutablePlaylist], faker: Faker):
        playlists = {pl.name: pl for pl in playlists}
        model.playlists.update(playlists, extract_keys=False)

        def _return_playlist(name: str, *_, **__) -> RemoteMutablePlaylist:
            return playlists[name]

        with (
            patch.object(PlaylistReadWriteSavedEndpoints, "get_or_create", side_effect=_return_playlist) as mock_get,
            patch.object(RemoteMutablePlaylist, "sync_items") as mock_sync,
        ):
            results = await model.sync_playlist_items()
            assert len(results) == len(playlists)

            assert mock_get.call_count == len(playlists)
            assert mock_sync.call_count == len(playlists)

            assert len(model.log_sync_playlist_items(results, skip_log=True)) == len(playlists)

    ###########################################################################
    ## Sync saved items
    ###########################################################################
    async def test_sync_saved_items(
            self,
            model: RemoteMutableLibrary,
            tracks: list[Track],
            faker: Faker,
    ):
        kind = faker.random_element(get_args(SYNC_TYPE))

        initial = [track.uri for track in tracks]
        add = faker.random_elements(initial)
        remove = faker.random_elements(initial, length=faker.random_int(0, len(add)))
        unchanged = faker.random_elements(initial)

        dry_run = faker.boolean()
        remote_uris = [SimpleURI.from_id(i, kind=RemoteTrack.type) for i in range(faker.random_int(1, 10))]

        with (
            patch.object(
                ReadSavedEndpoints, "get_all", return_value=remote_uris, new_callable=AsyncMock
            ) as mock_get_all,
            patch(
                "musify.models.collection.library.get_sync_items",
                return_value=(add, remove, unchanged)
            ) as mock_get_sync_items,
            patch.object(
                WriteSavedEndpoints, "add_many", return_value=len(add), new_callable=AsyncMock
            ) as mock_add,
            patch.object(
                WriteSavedEndpoints, "remove_many", return_value=len(remove), new_callable=AsyncMock
            ) as mock_remove,
        ):
            result = await model._sync_saved_items(
                kind=kind, items_type="tracks", items=tracks, api=model.api.tracks, dry_run=dry_run
            )

            mock_get_all.assert_called_once()
            mock_get_sync_items.assert_called_once_with(kind, initial=initial, remote=remote_uris)
            assert_sync_items_result(result, remote_uris, add, remove, unchanged)

            if dry_run:
                mock_add.assert_not_called()
                mock_remove.assert_not_called()
            else:
                if add:
                    mock_add.assert_called_once_with(add)
                else:
                    mock_add.assert_not_called()

                if remove:
                    mock_remove.assert_called_once_with(remove)
                else:
                    mock_remove.assert_not_called()

    @pytest.fixture
    def mock_sync_saved_items(self, model: RemoteMutableLibrary) -> Generator[Mock, None, None]:
        with patch.object(model.__class__, "_sync_saved_items") as mock_sync:
            yield mock_sync

    async def test_sync_tracks(self, model: RemoteMutableLibrary, mock_sync_saved_items: Mock, faker: Faker):
        kind = faker.random_element(get_args(SYNC_TYPE))
        dry_run = faker.boolean()

        await model.sync_tracks(kind=kind, dry_run=dry_run)
        mock_sync_saved_items.assert_called_once_with(
            kind, items_type="tracks", items=model.tracks, api=model.api.tracks, dry_run=dry_run
        )

    async def test_sync_artists(self, model: RemoteMutableLibrary, mock_sync_saved_items: Mock, faker: Faker):
        kind = faker.random_element(get_args(SYNC_TYPE))
        dry_run = faker.boolean()

        await model.sync_artists(kind=kind, dry_run=dry_run)
        mock_sync_saved_items.assert_called_once_with(
            kind, items_type="artists", items=model.artists, api=model.api.artists, dry_run=dry_run
        )

    async def test_sync_albums(self, model: RemoteMutableLibrary, mock_sync_saved_items: Mock, faker: Faker):
        kind = faker.random_element(get_args(SYNC_TYPE))
        dry_run = faker.boolean()

        await model.sync_albums(kind=kind, dry_run=dry_run)
        mock_sync_saved_items.assert_called_once_with(
            kind, items_type="albums", items=model.albums, api=model.api.albums, dry_run=dry_run
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
        dump = {faker.uuid4(): {"uri": pl.uri} for pl in playlists}
        expected = tuple({"uri": pl.uri} for pl in playlists)
        assert model._extract_playlists_from_backup(dump) == expected
        assert model._extract_playlists_from_backup({"playlists": dump}) == expected

        dump = [{"uri": pl.uri} for pl in playlists]
        assert model._extract_playlists_from_backup(dump) == expected
        assert model._extract_playlists_from_backup({"playlists": dump}) == expected

    @pytest.fixture
    def playlists_dump(self, playlists: list[Playlist]) -> list[dict[str, Any]]:
        return [
            {"name": pl.name, "uri": pl.uri, "tracks": [{"uri": str(tr.uri) for tr in pl.tracks}]}
            for pl in playlists
        ]

    @pytest.fixture
    def mock_extract_playlists_from_backup(
            self, model: RemoteMutableLibrary, playlists_dump: list[dict[str, Any]]
    ) -> Generator[Mock, None, None]:
        with patch.object(
                model.__class__, "_extract_playlists_from_backup", return_value=playlists_dump
        ) as mock_extract:
            yield mock_extract
            mock_extract.assert_called_once_with(playlists_dump)

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
    def mock_create_playlist(
            self, model: RemoteMutableLibrary, playlists: list[RemotePlaylist]
    ) -> Generator[Mock, None, None]:
        def _get_playlist(uri: str, *_, **__) -> RemotePlaylist:
            return next(pl for pl in playlists if str(pl.uri) == uri)

        with patch.object(
            PlaylistReadWriteSavedEndpoints, "create", side_effect=_get_playlist, new_callable=AsyncMock
        ) as mock_create:
            yield mock_create

    @pytest.fixture
    def mock_get_tracks(
            self, model: RemoteMutableLibrary, playlists: list[RemotePlaylist]
    ) -> Generator[Mock, None, None]:
        with patch.object(ReadItemsEndpoints, "get_many", new_callable=AsyncMock) as mock_get_tracks:
            yield mock_get_tracks

    @pytest.fixture
    def mock_sync_items(
            self, model: RemoteMutableLibrary, playlists: list[RemotePlaylist]
    ) -> Generator[Mock, None, None]:
        with patch.object(RemoteMutablePlaylist, "sync_items", new_callable=AsyncMock) as mock_sync_items:
            yield mock_sync_items

    async def test_restore_playlists_dry_run(
            self,
            model: RemoteMutableLibrary,
            playlists: list[RemotePlaylist],
            playlists_dump: list[dict[str, Any]],
            mock_extract_playlists_from_backup: Mock,
            mock_get_playlist: tuple[Mock, list[str]],
            mock_create_playlist: Mock,
            mock_get_tracks: Mock,
            mock_sync_items: Mock,
    ):
        result = await model.restore_playlists(playlists_dump, dry_run=True)
        assert len(result) == len(playlists)

        mock_get_playlist, failed = mock_get_playlist

        mock_create_playlist.assert_not_called()
        assert mock_get_tracks.call_count == len(playlists) - len(failed)
        assert mock_sync_items.call_count == len(playlists) - len(failed)

    async def test_restore_playlists(
            self,
            model: RemoteMutableLibrary,
            playlists: list[RemotePlaylist],
            playlists_dump: list[dict[str, Any]],
            mock_extract_playlists_from_backup: Mock,
            mock_get_playlist: tuple[Mock, list[str]],
            mock_create_playlist: Mock,
            mock_get_tracks: Mock,
            mock_sync_items: Mock,
    ):
        result = await model.restore_playlists(playlists_dump, dry_run=False)
        assert len(result) == len(playlists)

        mock_get_playlist, failed = mock_get_playlist

        assert mock_create_playlist.call_count == len(failed)
        assert mock_get_tracks.call_count == len(playlists)
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

    @pytest.fixture
    def mock_extract_uris_from_backup(self, model: RemoteMutableLibrary) -> Generator[Mock, None, None]:
        with patch.object(model.__class__, "_extract_uris_from_backup") as mock_extract:
            yield mock_extract

    async def test_restore_tracks(
            self,
            model: RemoteMutableLibrary,
            tracks: list[Track],
            mock_extract_uris_from_backup: Mock,
            faker: Faker,
    ):
        dry_run = faker.boolean()

        uris = [
            SimpleURI.from_id(faker.pystr(22, 22), kind=RemoteTrack.type)
            for _ in range(faker.random_int(1, 10))
        ]
        mock_extract_uris_from_backup.return_value = uris

        assert model.tracks != tracks

        with (
            patch.object(ReadItemsEndpoints, "get_many", return_value=tracks, new_callable=AsyncMock) as mock_get,
            patch.object(model.__class__, "sync_tracks", new_callable=AsyncMock) as mock_sync,
        ):
            await model.restore_tracks(uris, dry_run=dry_run)
            assert model.tracks == tracks

            mock_extract_uris_from_backup.assert_called_once_with(uris, key="tracks")
            mock_get.assert_called_once_with(uris)
            mock_sync.assert_called_once_with(kind="refresh", dry_run=dry_run)

    async def test_restore_artists(
            self,
            model: RemoteMutableLibrary,
            artists: list[Artist],
            mock_extract_uris_from_backup: Mock,
            faker: Faker,
    ):
        dry_run = faker.boolean()

        uris = [
            SimpleURI.from_id(faker.pystr(22, 22), kind=RemoteArtist.type)
            for _ in range(faker.random_int(1, 10))
        ]
        mock_extract_uris_from_backup.return_value = uris

        assert model.artists != artists

        with (
            patch.object(ReadItemsEndpoints, "get_many", return_value=artists, new_callable=AsyncMock) as mock_get,
            patch.object(model.__class__, "sync_artists", new_callable=AsyncMock) as mock_sync,
        ):
            await model.restore_artists(uris, dry_run=dry_run)
            assert model.artists == artists

            mock_extract_uris_from_backup.assert_called_once_with(uris, key="artists")
            mock_get.assert_called_once_with(uris)
            mock_sync.assert_called_once_with(kind="refresh", dry_run=dry_run)

    async def test_restore_albums(
            self,
            model: RemoteMutableLibrary,
            albums: list[Album],
            mock_extract_uris_from_backup: Mock,
            faker: Faker,
    ):
        dry_run = faker.boolean()

        uris = [
            SimpleURI.from_id(faker.pystr(22, 22), kind=RemoteAlbum.type)
            for _ in range(faker.random_int(1, 10))
        ]
        mock_extract_uris_from_backup.return_value = uris

        assert model.albums != albums

        with (
            patch.object(ReadItemsEndpoints, "get_many", return_value=albums, new_callable=AsyncMock) as mock_get,
            patch.object(model.__class__, "sync_albums", new_callable=AsyncMock) as mock_sync,
        ):
            await model.restore_albums(uris, dry_run=dry_run)
            assert model.albums == albums

            mock_extract_uris_from_backup.assert_called_once_with(uris, key="albums")
            mock_get.assert_called_once_with(uris)
            mock_sync.assert_called_once_with(kind="refresh", dry_run=dry_run)
