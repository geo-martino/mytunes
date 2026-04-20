from collections.abc import Generator, Collection
from typing import get_args, Any
from unittest.mock import patch, AsyncMock, Mock

import pytest
from faker import Faker
from pydantic import TypeAdapter, ValidationError
from pytest_mock import MockerFixture

from mytunes import MODULE_ROOT
# noinspection PyProtectedMember
from mytunes.core._collection._sync import SYNC_TYPE
from mytunes.core._collection.playlist import Playlist, HasPlaylists, HasMutablePlaylists, MutablePlaylist, \
    MergePlaylistsTypeAnnotated, RemotePlaylist, RemoteMutablePlaylist
from mytunes.core._context import RemoteModelContext
from mytunes.core._item.track import RemoteTrack
from mytunes.core._item.user import RemoteUser
from mytunes.core.api import RemoteAPI, CollectionWriteEndpoints
from mytunes.core.api.playlist import HasPlaylistEndpoints, PlaylistReadWriteEndpoints, PlaylistLibraryEndpoints
from mytunes.core.cursors import PageCursor
from mytunes.processors.compare import Comparer
from mytunes.processors.filters.compare import ComparerFilter
from mytunes.properties.uri import URI
from tests.core._collection.testers import RemoteCollectionTester
from tests.core._collection.utils import assert_sync_items_result
from tests.remote import SimpleURI, MockRemoteAPI
from tests.testers import BaseModelTester, NoUniqueKeyTester
from tests.utils import split_list


class TestPlaylist(NoUniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> Playlist:
        return Playlist(name=faker.sentence().rstrip("."))


class TestMutablePlaylist(NoUniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> MutablePlaylist:
        return MutablePlaylist(name=faker.sentence().rstrip("."))


class TestHasPlaylists(BaseModelTester):
    @pytest.fixture
    def model(self, playlists: list[Playlist]) -> HasPlaylists:
        return HasPlaylists(playlists=playlists)


class TestHasMutablePlaylists(BaseModelTester):
    @pytest.fixture
    def model(self, playlists: list[Playlist]) -> HasMutablePlaylists:
        return HasMutablePlaylists(playlists=playlists)

    @pytest.fixture
    def playlists(self, playlists: list[Playlist]) -> list[MutablePlaylist]:
        return [MutablePlaylist(**pl.model_dump()) for pl in playlists]

    def test_get_playlists_map_from_merge_input(self, model: HasMutablePlaylists):
        adapter = TypeAdapter(MergePlaylistsTypeAnnotated[MutablePlaylist])
        assert adapter.validate_python(None) is None

        playlists = model.playlists
        assert adapter.validate_python(playlists) is playlists
        assert adapter.validate_python(model) is playlists

        result = adapter.validate_python(list(playlists))
        assert result is not playlists
        assert result == playlists

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
        uri = SimpleURI.create_random(RemotePlaylist.type)
        return RemotePlaylist(name=faker.word(), owner=user, uri=uri, cursor=cursor)
    
    @pytest.fixture
    def owner(self, cursor: PageCursor, faker: Faker) -> RemoteUser:
        uri = SimpleURI.create_random(RemoteUser.type)
        return RemoteUser(name=faker.user_name(), uri=uri)
    
    def test_validate_mutability(self, model: RemotePlaylist, faker: Faker):
        context = RemoteModelContext(user=model.owner)

        # user is the owner, implies mutable
        with pytest.raises(ValidationError, match="implies that this playlist is mutable"):
            RemotePlaylist.model_validate(model, context=context)

    def test_validate_immutability(self, model: RemotePlaylist, faker: Faker):
        uri = SimpleURI.create_random(RemoteUser.type)
        user = RemoteUser(name=faker.user_name(), uri=uri)
        context = RemoteModelContext(user=user)

        # user is not the owner, implies immutable
        assert model == RemotePlaylist.model_validate(model, context=context)


class TestRemoteMutablePlaylist(RemoteCollectionTester):
    @pytest.fixture
    def model(
            self, tracks: list[RemoteTrack], owner: RemoteUser, cursor: PageCursor, faker: Faker
    ) -> RemoteMutablePlaylist:
        uri = SimpleURI.create_random(RemotePlaylist.type)
        return RemoteMutablePlaylist(name=faker.word(), owner=owner, uri=uri, cursor=cursor, tracks=tracks)

    @pytest.fixture
    def owner(self, cursor: PageCursor, faker: Faker) -> RemoteUser:
        uri = SimpleURI.create_random(RemoteUser.type)
        return RemoteUser(name=faker.user_name(), uri=uri)

    @pytest.fixture
    def tracks(self, tracks: list[RemoteTrack], faker: Faker) -> list[RemoteTrack]:
        return [
            RemoteTrack(
                **track.model_dump(exclude={"uri"}),
                uri=SimpleURI.create_random(RemoteTrack.type))
            for track in tracks
        ]

    def test_validate_mutability(self, model: RemotePlaylist, faker: Faker):
        # user is the owner, implies mutable
        context = RemoteModelContext(user=model.owner)
        assert model == RemoteMutablePlaylist.model_validate(model, context=context)

    def test_validate_immutability(self, model: RemotePlaylist, faker: Faker):
        uri = SimpleURI.create_random(RemoteUser.type)
        user = RemoteUser(name=faker.user_name(), uri=uri)
        context = RemoteModelContext(user=user)

        # user is not the owner, implies immutable
        with pytest.raises(ValidationError, match="implies that this playlist is immutable"):
            assert model == RemoteMutablePlaylist.model_validate(model, context=context)

    @pytest.fixture
    def api(self) -> RemoteAPI:
        return MockRemoteAPI()

    @pytest.fixture
    def mock_modify(self) -> Generator[Mock]:
        with patch.object(PlaylistLibraryEndpoints, "modify", new_callable=AsyncMock) as mock_modify:
            yield mock_modify

    async def test_sync_properties_dry_run(
            self, model: RemoteMutablePlaylist, api: HasPlaylistEndpoints, mock_modify: Mock, faker: Faker
    ):
        result = await model.sync_properties(api=api, dry_run=True)
        assert result == dict(name=model.name, description=model.description, public=model.public)
        mock_modify.assert_not_called()

    async def test_sync_properties(
            self, model: RemoteMutablePlaylist, api: HasPlaylistEndpoints, mock_modify: Mock, faker: Faker
    ):
        result = await model.sync_properties(api=api)
        assert result == dict(name=model.name, description=model.description, public=model.public)
        mock_modify.assert_called_once_with(model.uri.api_url, **result)

    @pytest.fixture(autouse=True)
    def mock_get_sync_items(self, tracks: list[RemoteTrack], faker: Faker) -> Generator[Mock]:
        initial = [track.uri for track in tracks]
        add = faker.random_elements(initial, unique=True)
        remove = faker.random_elements(initial, length=faker.random_int(0, len(add)), unique=True)
        unchanged = faker.random_elements(initial, unique=True)

        target = f"{MODULE_ROOT}.core._collection.playlist.get_sync_items"
        with patch(target, return_value=(add, remove, unchanged)) as mock_get_items:
            yield mock_get_items

    @pytest.fixture
    def uris(self, faker: Faker) -> list[URI]:
        return [SimpleURI.from_id(i, kind=RemoteTrack.type) for i in range(faker.random_int(1, 10))]

    @pytest.fixture(autouse=True)
    def mock_get_playlist_items(
            self, model: RemoteMutablePlaylist, uris: list[URI], faker: Faker
    ) -> Generator[Mock]:
        tracks = [RemoteTrack(name=faker.sentence().rstrip("."), uri=uri) for uri in uris]
        with (
            patch.object(
                PlaylistReadWriteEndpoints, "get", return_value=model, new_callable=AsyncMock
            ),
            patch.object(
                PlaylistReadWriteEndpoints, "get_all", return_value=tracks, new_callable=AsyncMock
            ) as mock_get_all
        ):
            yield mock_get_all

    # noinspection PyUnusedLocal
    @staticmethod
    def _return_length(url: Any, uris: Collection, *_, **__) -> int:
        return len(uris)

    @pytest.fixture(autouse=True)
    def mock_add(self) -> Generator[Mock]:
        with patch.object(
                CollectionWriteEndpoints, "add", side_effect=self._return_length, new_callable=AsyncMock
        ) as mock_add:
            yield mock_add

    @pytest.fixture(autouse=True)
    def mock_remove(self) -> Generator[Mock]:
        with patch.object(
                CollectionWriteEndpoints, "remove", side_effect=self._return_length, new_callable=AsyncMock
        ) as mock_remove:
            yield mock_remove

    async def test_sync_items(
            self,
            model: RemoteMutablePlaylist,
            tracks: list[RemoteTrack],
            api: HasPlaylistEndpoints,
            mock_get_playlist_items: Mock,
            mock_get_sync_items: Mock,
            mock_add: Mock,
            mock_remove: Mock,
            faker: Faker,
    ):
        kind = faker.random_element(get_args(SYNC_TYPE))

        initial = [track.uri for track in tracks]
        add, remove, unchanged = mock_get_sync_items.return_value
        remote = mock_get_playlist_items.return_value
        remote_uris = [item.uri for item in remote]

        assert model.tracks == tracks

        result = await model.sync_items(api, kind=kind, dry_run=False)
        assert_sync_items_result(result, remote, add, remove, unchanged)

        mock_get_playlist_items.assert_called_once_with(model)
        mock_get_sync_items.assert_called_once_with(kind, initial=initial, remote=remote_uris)

        mock_add.assert_called_once_with(model.uri.api_url, uris=add)
        mock_remove.assert_called_once_with(model.uri.api_url, uris=remove)

    async def test_sync_items_dry_run(
            self,
            model: RemoteMutablePlaylist,
            tracks: list[RemoteTrack],
            api: HasPlaylistEndpoints,
            mock_get_playlist_items: Mock,
            mock_get_sync_items: Mock,
            mock_add: Mock,
            mock_remove: Mock,
            faker: Faker,
    ):
        kind = faker.random_element(get_args(SYNC_TYPE))

        initial = [track.uri for track in tracks]
        add, remove, unchanged = mock_get_sync_items.return_value
        remote = mock_get_playlist_items.return_value
        remote_uris = [item.uri for item in remote]

        assert model.tracks == tracks

        result = await model.sync_items(api, kind=kind, dry_run=True)
        assert_sync_items_result(result, remote, add, remove, unchanged)

        mock_get_playlist_items.assert_called_once_with(model)
        mock_get_sync_items.assert_called_once_with(kind, initial=initial, remote=remote_uris)

        mock_add.assert_not_called()
        mock_remove.assert_not_called()

    async def test_sync_items_applies_filter(
            self,
            model: RemoteMutablePlaylist,
            tracks: list[RemoteTrack],
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
