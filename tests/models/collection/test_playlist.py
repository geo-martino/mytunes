from collections.abc import Generator, Collection
from typing import get_args, Any
from unittest.mock import patch, AsyncMock, Mock

import pytest
from faker import Faker
from pydantic import TypeAdapter
from pytest_mock import MockerFixture

from musify import MODULE_ROOT
from musify.models._context import RemoteModelContext
from musify.models.api import RemoteAPI, WriteCollectionEndpoints
from musify.models.api.playlist import HasPlaylistEndpoints
# noinspection PyProtectedMember
from musify.models.collection._sync import SYNC_TYPE
from musify.models.collection.playlist import Playlist, HasPlaylists, HasMutablePlaylists, MutablePlaylist, \
    MergePlaylistsTypeAnnotated, RemotePlaylist, RemoteMutablePlaylist
from musify.models.cursors import PageCursor
from musify.models.item.track import RemoteTrack, Track
from musify.models.properties.uri import URI
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
            faker.pystr(22, 22), kind=Playlist.type
        )
        return Playlist(name=faker.sentence(), uri=uri)


class TestMutablePlaylist(NoUniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> MutablePlaylist:
        uri = SimpleURI.from_id(
            faker.pystr(22, 22), kind=MutablePlaylist.type
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

    def test_merge_playlists(self, model: HasMutablePlaylists, playlists: list[MutablePlaylist], mocker: MockerFixture):
        initial, other, overlap = split_list(playlists, 2, 6)
        model = HasMutablePlaylists(playlists=initial)

        mock_merge = mocker.spy(MutablePlaylist, "merge")

        model.merge_playlists(playlists)

        assert len(mock_merge.mock_calls) == len(initial)
        assert len(model.playlists) == len(playlists)


class TestRemotePlaylist(RemoteCollectionTester):
    @pytest.fixture
    def model(self, user: RemoteUser, cursor: PageCursor, faker: Faker) -> RemotePlaylist:
        uri = SimpleURI.from_id(
            faker.pystr(22, 22), kind=RemotePlaylist.type
        )
        return RemotePlaylist(
            name=faker.word(),
            owner=user,
            uri=uri,
            total=faker.random_int(1, 20),
            cursor=cursor
        )
    
    @pytest.fixture
    def owner(self, cursor: PageCursor, faker: Faker) -> RemoteUser:
        uri = SimpleURI.from_id(faker.pystr(22, 22), kind=RemoteUser.type)
        return RemoteUser(name=faker.user_name(), uri=uri)
    
    def test_validate_mutability(self, model: RemotePlaylist, faker: Faker):
        context = RemoteModelContext(user=model.owner)

        # user is the owner, implies mutable
        with pytest.raises(ValueError, match="implies that this playlist is mutable"):
            RemotePlaylist.model_validate(model, context=context)

    def test_validate_immutability(self, model: RemotePlaylist, faker: Faker):
        uri = SimpleURI.from_id(faker.pystr(22, 22), kind=RemoteUser.type)
        user = RemoteUser(name=faker.user_name(), uri=uri)
        context = RemoteModelContext(user=user)

        # user is not the owner, implies immutable
        assert model == RemotePlaylist.model_validate(model, context=context)


class TestRemoteMutablePlaylist(RemoteCollectionTester):
    @pytest.fixture
    def model(
            self, tracks: list[RemoteTrack], owner: RemoteUser, cursor: PageCursor, faker: Faker
    ) -> RemoteMutablePlaylist:
        uri = SimpleURI.from_id(
            faker.pystr(22, 22), kind=RemotePlaylist.type
        )
        return RemoteMutablePlaylist(
            name=faker.word(),
            owner=owner,
            uri=uri,
            total=faker.random_int(1, 20),
            cursor=cursor,
            tracks=tracks,
        )

    @pytest.fixture
    def owner(self, cursor: PageCursor, faker: Faker) -> RemoteUser:
        uri = SimpleURI.from_id(faker.pystr(22, 22), kind=RemoteUser.type)
        return RemoteUser(name=faker.user_name(), uri=uri)

    @pytest.fixture
    def tracks(self, tracks: list[Track], faker: Faker) -> list[RemoteTrack]:
        return [
            RemoteTrack(
                **track.model_dump(exclude={"uri"}),
                uri=SimpleURI.from_id(faker.pystr(22, 22), kind=RemoteTrack.type)
            )
            for track in tracks
        ]

    def test_validate_mutability(self, model: RemotePlaylist, faker: Faker):
        # user is the owner, implies mutable
        context = RemoteModelContext(user=model.owner)
        assert model == RemoteMutablePlaylist.model_validate(model, context=context)

    def test_validate_immutability(self, model: RemotePlaylist, faker: Faker):
        uri = SimpleURI.from_id(faker.pystr(22, 22), kind=RemoteUser.type)
        user = RemoteUser(name=faker.user_name(), uri=uri)
        context = RemoteModelContext(user=user)

        # user is not the owner, implies immutable
        with pytest.raises(ValueError, match="implies that this playlist is immutable"):
            assert model == RemoteMutablePlaylist.model_validate(model, context=context)

    @pytest.fixture
    def api(self) -> RemoteAPI:
        return MockRemoteAPI()

    @pytest.fixture(autouse=True)
    def mock_get_sync_items(self, tracks: list[RemoteTrack], faker: Faker) -> Generator[Mock, None, None]:
        initial = [track.uri for track in tracks]
        add = faker.random_elements(initial)
        remove = faker.random_elements(initial, length=faker.random_int(0, len(add)))
        unchanged = faker.random_elements(initial)

        target = f"{MODULE_ROOT}.models.collection.playlist.get_sync_items"
        with patch(target, return_value=(add, remove, unchanged)) as mock_get_items:
            yield mock_get_items

    @pytest.fixture
    def uris(self, faker: Faker) -> list[URI]:
        return [SimpleURI.from_id(i, kind=RemoteTrack.type) for i in range(faker.random_int(1, 10))]

    @pytest.fixture(autouse=True)
    def mock_get_remote_uris(self, model: RemoteMutablePlaylist, uris: list[URI]) -> Generator[Mock, None, None]:
        with patch.object(model, "_get_remote_uris", return_value=uris) as mock_get_uris:
            yield mock_get_uris

    # noinspection PyUnusedLocal
    @staticmethod
    def _return_length(url: Any, uris: Collection, *_, **__) -> int:
        return len(uris)

    @pytest.fixture(autouse=True)
    def mock_add(self) -> Generator[Mock, None, None]:
        with patch.object(
                WriteCollectionEndpoints, "add", side_effect=self._return_length, new_callable=AsyncMock
        ) as mock_add:
            yield mock_add

    @pytest.fixture(autouse=True)
    def mock_remove(self) -> Generator[Mock, None, None]:
        with patch.object(
                WriteCollectionEndpoints, "remove", side_effect=self._return_length, new_callable=AsyncMock
        ) as mock_remove:
            yield mock_remove

    async def test_sync_items(
            self,
            model: RemoteMutablePlaylist,
            tracks: list[RemoteTrack],
            api: HasPlaylistEndpoints,
            mock_get_remote_uris: Mock,
            mock_get_sync_items: Mock,
            mock_add: Mock,
            mock_remove: Mock,
            faker: Faker,
    ):
        kind = faker.random_element(get_args(SYNC_TYPE))

        initial = [track.uri for track in tracks]
        add, remove, unchanged = mock_get_sync_items.return_value
        remote = mock_get_remote_uris.return_value
        show_bar = faker.boolean()

        assert model.tracks == tracks

        result = await model.sync_items(api, kind=kind, dry_run=False, show_bar=show_bar)
        assert_sync_items_result(result, remote, add, remove, unchanged)

        mock_get_remote_uris.assert_called_once_with(api, show_bar=show_bar)
        mock_get_sync_items.assert_called_once_with(kind, initial=initial, remote=remote)

        mock_add.assert_called_once_with(model.uri.api_url, uris=add, show_bar=show_bar)
        mock_remove.assert_called_once_with(model.uri.api_url, uris=remove, show_bar=show_bar)

    async def test_sync_items_dry_run(
            self,
            model: RemoteMutablePlaylist,
            tracks: list[RemoteTrack],
            api: HasPlaylistEndpoints,
            mock_get_remote_uris: Mock,
            mock_get_sync_items: Mock,
            mock_add: Mock,
            mock_remove: Mock,
            faker: Faker,
    ):
        kind = faker.random_element(get_args(SYNC_TYPE))

        initial = [track.uri for track in tracks]
        add, remove, unchanged = mock_get_sync_items.return_value
        remote = mock_get_remote_uris.return_value
        show_bar = faker.boolean()

        assert model.tracks == tracks

        result = await model.sync_items(api, kind=kind, dry_run=True, show_bar=show_bar)
        assert_sync_items_result(result, remote, add, remove, unchanged)

        mock_get_remote_uris.assert_called_once_with(api, show_bar=show_bar)
        mock_get_sync_items.assert_called_once_with(kind, initial=initial, remote=remote)

        mock_add.assert_not_called()
        mock_remove.assert_not_called()

    async def test_sync_items_applies_filter(
            self,
            model: RemoteMutablePlaylist,
            tracks: list[Track],
            api: HasPlaylistEndpoints,
            mock_get_sync_items: Mock,
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

        await model.sync_items(api, items_filter=items_filter)

        result = mock_get_sync_items.call_args.kwargs["initial"]
        assert sorted(result) == sorted(track.uri for track in expected)
