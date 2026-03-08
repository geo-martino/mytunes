from unittest.mock import patch

import pytest
from faker import Faker
from pydantic import TypeAdapter

from musify.models.collection.playlist import Playlist, HasPlaylists, HasMutablePlaylists, MutablePlaylist, \
    MergePlaylistsTypeAnnotated
from tests.models.testers import MusifyModelTester, UniqueKeyTester
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


class TestHasPlaylists(MusifyModelTester):
    @pytest.fixture
    def model(self, playlists: list[Playlist]) -> HasPlaylists:
        return HasPlaylists(playlists=playlists)


class TestHasMutablePlaylists(MusifyModelTester):
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
