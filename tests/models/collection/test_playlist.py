from typing import get_args
from unittest.mock import patch, AsyncMock

import pytest
from faker import Faker
from pydantic import TypeAdapter

from musify.models.api import RemoteAPI, WriteCollectionEndpoints
from musify.models.api.playlist import HasPlaylistEndpoints
# noinspection PyProtectedMember
from musify.models.collection._sync import SYNC_TYPE
from musify.models.collection.playlist import Playlist, HasPlaylists, HasMutablePlaylists, MutablePlaylist, \
    MergePlaylistsTypeAnnotated, RemotePlaylist, RemoteMutablePlaylist
from musify.models.cursors import PageCursor
from musify.models.item.track import RemoteTrack, Track
from musify.models.user import RemoteUser
from musify.processors_new.compare import Comparer
from musify.processors_new.filters import ComparerFilter
from tests.models.api.utils import MockRemoteAPI
from tests.models.collection.testers import RemoteCollectionTester
from tests.models.collection.utils import assert_sync_items_result
from tests.models.testers import BaseModelTester, NoUniqueKeyTester
from tests.utils import split_list, SimpleURI


class TestPlaylist(NoUniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> Playlist:
        uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=Playlist.type
        )
        return Playlist(name=faker.sentence(), uri=uri)


class TestMutablePlaylist(NoUniqueKeyTester):
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
        return HasMutablePlaylists(playlists=playlists)

    @pytest.fixture
    def playlists(self, playlists: list[Playlist]) -> list[MutablePlaylist]:
        return [MutablePlaylist(**pl.model_dump()) for pl in playlists]

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
    def model(self, tracks: list[RemoteTrack], cursor: PageCursor, faker: Faker) -> RemoteMutablePlaylist:
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
            cursor=cursor,
            tracks=tracks,
        )

    @pytest.fixture
    def tracks(self, tracks: list[Track], faker: Faker) -> list[RemoteTrack]:
        return [
            RemoteTrack(
                **track.model_dump(exclude={"uri"}),
                uri=SimpleURI.from_id(faker.pystr(22, 22), kind=RemoteTrack.type)
            )
            for track in tracks
        ]

    @pytest.fixture
    def api(self) -> RemoteAPI:
        return MockRemoteAPI()

    async def test_sync_items(
            self,
            model: RemoteMutablePlaylist,
            tracks: list[RemoteTrack],
            api: HasPlaylistEndpoints,
            faker: Faker,
    ):
        kind = faker.random_element(get_args(SYNC_TYPE))

        assert model.tracks == tracks
        initial = [track.uri for track in tracks]
        add = faker.random_elements(initial)
        remove = faker.random_elements(initial, length=faker.random_int(0, len(add)))
        unchanged = faker.random_elements(initial)

        remote_uris = [SimpleURI.from_id(i, kind=RemoteTrack.type) for i in range(faker.random_int(1, 10))]
        dry_run = faker.boolean()
        show_bar = faker.boolean()

        with (
            patch.object(model, "_get_remote_uris", return_value=remote_uris) as mock_get_remote_uris,
            patch(
                "musify.models.collection.playlist.get_sync_items",
                return_value=(add, remove, unchanged)
            ) as mock_get_items,
            patch.object(
                WriteCollectionEndpoints, "add", return_value=len(add), new_callable=AsyncMock
            ) as mock_add,
            patch.object(
                WriteCollectionEndpoints, "remove", return_value=len(remove), new_callable=AsyncMock
            ) as mock_remove,
        ):
            result = await model.sync_items(api, kind=kind, dry_run=dry_run, show_bar=show_bar)

            mock_get_remote_uris.assert_called_once_with(api, show_bar=show_bar)
            mock_get_items.assert_called_once_with(kind, initial=initial, remote=remote_uris)
            assert_sync_items_result(result, remote_uris, add, remove, unchanged)

            if dry_run:
                mock_add.assert_not_called()
                mock_remove.assert_not_called()
            else:
                mock_add.assert_called_once_with(model.uri.api_url, uris=add, show_bar=show_bar)
                mock_remove.assert_called_once_with(model.uri.api_url, uris=remove, show_bar=show_bar)

    async def test_sync_items_applies_filter(
            self,
            model: RemoteMutablePlaylist,
            tracks: list[Track],
            api: HasPlaylistEndpoints,
            faker: Faker,
    ):
        assert model.tracks == tracks
        expected = faker.random_elements(tracks, unique=True)

        items_filter = ComparerFilter(
            comparers=Comparer(
                field="name",
                condition="is in",
                expected=[track.name for track in expected]
            )
        )

        with (
            patch.object(model, "_get_remote_uris", return_value=[]),
            patch("musify.models.collection.playlist.get_sync_items", return_value=([], [], [])) as mock_get_items,
            patch.object(WriteCollectionEndpoints, "add", new_callable=AsyncMock),
            patch.object(WriteCollectionEndpoints, "remove", new_callable=AsyncMock),
        ):
            await model.sync_items(api, items_filter=items_filter)

            result = mock_get_items.call_args.kwargs["initial"]
            assert sorted(result) == sorted(track.uri for track in expected)
