from unittest.mock import patch

import pytest
from faker import Faker
from pydantic import TypeAdapter

from musify.models.collection.playlist import Playlist, HasPlaylists, HasMutablePlaylists, MutablePlaylist, \
    MergePlaylistsTypeAnnotated, RemotePlaylist, RemoteMutablePlaylist
from musify.models.cursors import PageCursor
from musify.models.user import RemoteUser
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
        return HasMutablePlaylists(playlists=playlists)

    def test_get_playlists_map_from_merge_input(self, model: HasMutablePlaylists):
        adapter = TypeAdapter(MergePlaylistsTypeAnnotated)
        assert adapter.validate_python(None) is None
        playlists = model.playlists
        assert adapter.validate_python(playlists) is playlists
        assert adapter.validate_python(model) is playlists

        assert adapter.validate_python(dict(playlists)) is not playlists
        assert adapter.validate_python(dict(playlists)) == playlists

    def test_merge_playlists(self, model: HasMutablePlaylists, playlists: list[Playlist]):
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
