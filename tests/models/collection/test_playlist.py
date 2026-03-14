from unittest.mock import patch, AsyncMock

import pytest
from faker import Faker
from pydantic import TypeAdapter

from musify.exception import MusifyValueError
from musify.models.api import RemoteAPI, ReadCollectionEndpoints, WriteCollectionEndpoints
from musify.models.api.playlist import HasPlaylistEndpoints, PlaylistReadWriteEndpoints
from musify.models.collection.playlist import Playlist, HasPlaylists, HasMutablePlaylists, MutablePlaylist, \
    MergePlaylistsTypeAnnotated, RemotePlaylist, RemoteMutablePlaylist, SyncResultRemotePlaylist
from musify.models.cursors import PageCursor
from musify.models.item.track import RemoteTrack
from musify.models.properties.uri import URI
from musify.models.user import RemoteUser
from tests.models.api.utils import MockRemoteAPI, MockInitialCursor
from tests.models.collection.testers import RemoteCollectionTester
from tests.models.testers import BaseModelTester, UniqueKeyTester
from tests.utils import split_list, SimpleURI


class TestPlaylist(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> Playlist:
        uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=Playlist.type
        )
        return Playlist(name=faker.sentence(), uri=uri)


class TestMutablePlaylist(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> MutablePlaylist:
        uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=MutablePlaylist.type
        )
        return MutablePlaylist(name=faker.sentence(), uri=uri)


class TestHasPlaylists(BaseModelTester):
    @pytest.fixture
    def model(self, playlists: list[Playlist]) -> HasPlaylists:
        return HasPlaylists(playlists=playlists)

    def test_items_count(self, playlists: list[Playlist]):
        model = HasPlaylists(playlists=playlists)
        assert model.count == len(playlists)


class TestHasMutablePlaylists(BaseModelTester):
    @pytest.fixture
    def model(self, playlists: list[Playlist]) -> HasMutablePlaylists:
        playlists = [MutablePlaylist(**pl.model_dump()) for pl in playlists]
        return HasMutablePlaylists(playlists=playlists)

    def test_get_playlists_map_from_merge_input(self, model: HasMutablePlaylists):
        adapter = TypeAdapter(MergePlaylistsTypeAnnotated)
        assert adapter.validate_python(None) is None
        playlists = model.playlists
        assert adapter.validate_python(playlists) is playlists
        assert adapter.validate_python(model) is playlists

        assert adapter.validate_python(dict(playlists)) is not playlists
        assert adapter.validate_python(dict(playlists)) == playlists

    def test_merge_playlists(self, model: HasMutablePlaylists, playlists: list[MutablePlaylist]):
        initial, other, overlap = split_list(playlists, 2, 6)
        model = HasMutablePlaylists(playlists=initial)

        with patch.object(initial[0].__class__, "merge") as mock_merge:
            model.merge_playlists(playlists)
            assert len(mock_merge.mock_calls) == len(initial)
            assert len(model.playlists) == len(playlists)


class TestRemotePlaylist(RemoteCollectionTester):
    @pytest.fixture
    def model(self, cursor: PageCursor, faker: Faker) -> RemotePlaylist:
        playlist_uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=RemotePlaylist.type
        )
        owner_uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=RemoteUser.type
        )
        return RemotePlaylist(
            name=faker.word(),
            owner=RemoteUser(name=faker.user_name(), uri=owner_uri),
            uri=playlist_uri,
            total=faker.random_int(1, 20),
            cursor=cursor
        )


class TestRemoteMutablePlaylist(RemoteCollectionTester):
    @pytest.fixture
    def model(self, cursor: PageCursor, faker: Faker) -> RemoteMutablePlaylist:
        playlist_uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=RemotePlaylist.type
        )
        owner_uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=RemoteUser.type
        )
        return RemoteMutablePlaylist(
            name=faker.word(),
            owner=RemoteUser(name=faker.user_name(), uri=owner_uri),
            uri=playlist_uri,
            total=faker.random_int(1, 20),
            cursor=cursor
        )

    @pytest.fixture
    def api(self) -> RemoteAPI:
        return MockRemoteAPI()

    @pytest.fixture
    def initial_uris(self, model: RemoteMutablePlaylist, faker: Faker) -> list[URI]:
        initial = [SimpleURI.from_id(i, kind=RemoteTrack.type) for i in range(faker.random_int(1, 10))]
        model.tracks[:] = [RemoteTrack(name=faker.name(), uri=uri) for uri in initial]
        return initial

    @pytest.fixture
    def remote_uris(self, model: RemoteMutablePlaylist, faker: Faker) -> list[URI]:
        return [SimpleURI.from_id(i, kind=RemoteTrack.type) for i in range(faker.random_int(1, 10))]

    def test_get_sync_items_for_add(self, model: RemoteMutablePlaylist, faker: Faker):
        initial = [SimpleURI.from_id(i, kind=RemoteTrack.type) for i in range(faker.random_int(10, 15))]
        remote = [SimpleURI.from_id(i, kind=RemoteTrack.type) for i in range(faker.random_int(1, 10))]

        add, remove, unchanged = model._get_sync_items_for_add(initial, remote)
        assert add == initial[len(remote):]
        assert remove == []
        assert unchanged == remote

    def test_get_sync_items_for_refresh(self, model: RemoteMutablePlaylist, faker: Faker):
        initial = [SimpleURI.from_id(i, kind=RemoteTrack.type) for i in range(faker.random_int(10, 15))]
        remote = [SimpleURI.from_id(i, kind=RemoteTrack.type) for i in range(faker.random_int(1, 10))]

        add, remove, unchanged = model._get_sync_items_for_refresh(initial, remote)
        assert add == initial
        assert remove == remote
        assert unchanged == []

    def test_get_sync_items_for_sync(self, model: RemoteMutablePlaylist, faker: Faker):
        initial = [SimpleURI.from_id(i, kind=RemoteTrack.type) for i in range(faker.random_int(5, 15))]
        remote = [SimpleURI.from_id(i, kind=RemoteTrack.type) for i in range(faker.random_int(1, 10))]
        remote += [
            SimpleURI.from_id(i + len(initial) + len(remote), kind=RemoteTrack.type)
            for i in range(faker.random_int(1, 10))
        ]

        add, remove, unchanged = model._get_sync_items_for_sync(initial, remote)
        assert add == sorted(set(initial) - set(remote), key=lambda uri: int(uri.id))
        assert remove == sorted(set(remote) - set(initial), key=lambda uri: int(uri.id))
        assert unchanged == sorted(set(initial) & set(remote), key=lambda uri: int(uri.id))

    async def test_sync_calls_expected_getter(
            self,
            model: RemoteMutablePlaylist,
            api: HasPlaylistEndpoints,
            initial_uris: list[URI],
            remote_uris: list[URI],
            faker: Faker,
    ):
        with (
            patch.object(model, "_get_remote_uris", return_value=remote_uris) as mock_get_remote,
            patch.object(model, "_get_sync_items_for_add", return_value=([], [], [])) as mock_add,
            patch.object(model, "_get_sync_items_for_refresh", return_value=([], [], [])) as mock_refresh,
            patch.object(model, "_get_sync_items_for_sync", return_value=([], [], [])) as mock_sync,
        ):
            await model.sync(api, kind="new")
            assert mock_get_remote.call_count == 1
            mock_add.assert_called_once_with(initial_uris, remote_uris)
            mock_refresh.assert_not_called()
            mock_sync.assert_not_called()

            await model.sync(api, kind="refresh")
            assert mock_get_remote.call_count == 2
            mock_add.assert_called_once_with(initial_uris, remote_uris)
            mock_refresh.assert_called_with(initial_uris, remote_uris)
            mock_sync.assert_not_called()

            await model.sync(api, kind="sync")
            assert mock_get_remote.call_count == 3
            mock_add.assert_called_with(initial_uris, remote_uris)
            mock_refresh.assert_called_with(initial_uris, remote_uris)
            mock_sync.assert_called_with(initial_uris, remote_uris)

    async def test_sync_fails_on_unknown_type(self, model: RemoteMutablePlaylist, api: HasPlaylistEndpoints):
        with (
            patch.object(model, "_get_remote_uris", return_value=[]),
            pytest.raises(MusifyValueError, match="Invalid sync type")
        ):
            await model.sync(api, kind="unknown")

    @staticmethod
    def assert_sync_result(
            result: SyncResultRemotePlaylist,
            initial_uris: list[URI],
            remote_uris: list[URI],
            unchanged: set[URI],
    ):
        assert result.start == len(remote_uris)
        assert result.added == len(initial_uris)
        assert result.removed == len(remote_uris)
        assert result.unchanged == len(unchanged)
        assert result.difference == len(initial_uris) - len(remote_uris)
        assert result.final == len(initial_uris)

    async def test_sync_dry_run(
            self,
            model: RemoteMutablePlaylist,
            api: HasPlaylistEndpoints,
            initial_uris: list[URI],
            remote_uris: list[URI],
            faker: Faker,
    ):
        unchanged = set(initial_uris) & set(remote_uris)

        with (
            patch.object(model, "_get_remote_uris", return_value=remote_uris),
            patch.object(model, "_get_sync_items_for_sync", return_value=(initial_uris, remote_uris, unchanged)),
            patch.object(WriteCollectionEndpoints, "append", new_callable=AsyncMock) as mock_append,
            patch.object(WriteCollectionEndpoints, "remove", new_callable=AsyncMock) as mock_remove,
        ):
            result = await model.sync(api, kind="sync", dry_run=True)

            mock_append.assert_not_called()
            mock_remove.assert_not_called()
            self.assert_sync_result(result, initial_uris, remote_uris, unchanged)

    async def test_sync(
            self,
            model: RemoteMutablePlaylist,
            api: HasPlaylistEndpoints,
            initial_uris: list[URI],
            remote_uris: list[URI],
            faker: Faker,
    ):
        unchanged = set(initial_uris) & set(remote_uris)

        with (
            patch.object(model, "_get_remote_uris", return_value=remote_uris),
            patch.object(model, "_get_sync_items_for_sync", return_value=(initial_uris, remote_uris, unchanged)),
            patch.object(
                WriteCollectionEndpoints, "append", return_value=len(initial_uris), new_callable=AsyncMock
            ) as mock_append,
            patch.object(
                WriteCollectionEndpoints, "remove", return_value=len(remote_uris), new_callable=AsyncMock
            ) as mock_remove,
        ):
            result = await model.sync(api, kind="sync", dry_run=False)

            mock_append.assert_called_once_with(model.uri.api_url, uris=initial_uris)
            mock_remove.assert_called_once_with(model.uri.api_url, uris=remote_uris)
            self.assert_sync_result(result, initial_uris, remote_uris, unchanged)
