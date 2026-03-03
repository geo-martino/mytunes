from unittest.mock import patch

import pytest
from faker import Faker

from musify.models.collection.playlist import Playlist, HasPlaylists, HasMutablePlaylists, MutablePlaylist
from musify.models.properties.uri import URI
from tests.models.testers import MusifyModelTester, UniqueKeyTester
from tests.utils import split_list, SimpleURI


class TestPlaylist(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> Playlist:
        uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=Playlist.type, source=faker.word()
        )
        return Playlist(name=faker.sentence(), uri=uri)


class TestMutablePlaylist(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> MutablePlaylist:
        uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=MutablePlaylist.type, source=faker.word()
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
        assert model._get_playlists_map_from_merge_input(None) is None
        playlists = model.playlists
        assert model._get_playlists_map_from_merge_input(playlists) is playlists
        assert model._get_playlists_map_from_merge_input(model) is playlists

        assert model._get_playlists_map_from_merge_input(dict(playlists)) is not playlists
        assert model._get_playlists_map_from_merge_input(dict(playlists)) == playlists

    def test_merge_playlists(self, model: HasMutablePlaylists, playlists: list[Playlist]):
        initial, other, overlap = split_list(playlists, 2, 6)
        model = HasMutablePlaylists(playlists=initial)

        with patch.object(initial[0].__class__, "merge") as mock_merge:
            model.merge_playlists(playlists)
            assert len(mock_merge.mock_calls) == len(initial)
            assert len(model.playlists) == len(playlists)
