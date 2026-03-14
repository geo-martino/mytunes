from collections.abc import Collection
from typing import ClassVar, Generator
from unittest.mock import patch, Mock

import pytest
from faker import Faker
from fontTools.misc.cython import returns

from musify.models.api import RemoteAPI, ReadSavedEndpoints
from musify.models.api.playlist import PlaylistReadWriteSavedEndpoints
# noinspection PyProtectedMember
from musify.models.collection.library import HasTracksAndPlaylists, RemoteLibrary, RemoteMutableLibrary
from musify.models.collection.playlist import Playlist, RemotePlaylist, RemoteMutablePlaylist
from musify.models.item.album import Album, RemoteAlbum
from musify.models.item.artist import Artist, RemoteArtist
from musify.models.item.track import Track, RemoteTrack
from musify.models.remote import RemoteResource
from musify.models.user import RemoteUser
from tests.models.api.utils import MockRemoteAPI, MockUrlCursor
from tests.models.testers import BaseResourceTester, BaseModelTester
from tests.utils import SimpleURI


class TestLibrary(BaseResourceTester):
    @pytest.fixture
    def model(self, faker: Faker) -> HasTracksAndPlaylists:
        return HasTracksAndPlaylists()

    def test_tracks_in_playlists(self, tracks: list[Track], playlists: list[Playlist]):
        for pl in playlists:
            tracks += pl.tracks[:len(pl.tracks) // 2]

        library = HasTracksAndPlaylists(tracks=tracks, playlists=playlists)
        assert all(track not in library.tracks for track in library.tracks_in_playlists)
        assert library.tracks_in_playlists == [track for pl in playlists for track in pl.tracks]

    def test_items_count(self, tracks: list[Track], playlists: list[Playlist]):
        library = HasTracksAndPlaylists(tracks=tracks, playlists=playlists)
        assert library.count == len(tracks)


class MockRemoteLibrary(RemoteLibrary):
    source: ClassVar[str] = "test"


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
    def playlists(
            self, playlists: list[Playlist], tracks: list[Track], user: RemoteUser, faker: Faker
    ) -> list[RemotePlaylist]:
        return [
            RemotePlaylist(
                **pl.model_dump(exclude={"tracks"}),
                owner=RemoteUser(name=faker.name(), uri=SimpleURI.from_id(faker.pystr(22, 22), kind=RemoteUser.type)),
                cursor=MockUrlCursor(url=faker.url()),
                tracks=faker.random_elements(tracks),
            )
            for pl in playlists
        ]

    @pytest.fixture
    def tracks(self, tracks: list[Track]) -> list[RemoteTrack]:
        return [RemoteTrack(**track.model_dump()) for track in tracks]

    @pytest.fixture
    def artists(self, artists: list[Artist]) -> list[RemoteArtist]:
        return [RemoteArtist(**artist.model_dump()) for artist in artists]

    @pytest.fixture
    def albums(self, albums: list[Album]) -> list[RemoteAlbum]:
        return [RemoteAlbum(**album.model_dump()) for album in albums]

    @pytest.fixture
    def mock_get_all(self) -> Generator[Mock, None, None]:
        with patch.object(ReadSavedEndpoints, "get_all") as mock_get_all:
            yield mock_get_all

    @staticmethod
    def assert_items_loaded(loaded_items: Collection[RemoteResource], mock_get_all: Mock) -> None:
        """Assert that the given tracks were loaded into the model"""
        mock_get_all.assert_called_once()
        assert len(loaded_items) == len(mock_get_all.return_value)
        assert [item.uri for item in loaded_items] == [item.uri for item in mock_get_all.return_value]

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

    def test_generate_backup(
            self,
            model: RemoteLibrary,
            api: RemoteAPI,
            playlists: list[RemotePlaylist],
            tracks: list[RemoteTrack],
            albums: list[RemoteAlbum],
            artists: list[RemoteArtist],
    ):
        model = model.__class__(api=api, playlists=playlists, tracks=tracks, albums=albums, artists=artists)

        backup = model.generate_backup()
        assert len(backup["playlists"]) == len(model.playlists)
        for pl, pl_backup in zip(playlists, backup["playlists"]):
            assert isinstance(pl_backup, dict)
            assert "name" in pl_backup and isinstance(pl_backup["name"], str)
            assert "tracks" in pl_backup and len(pl_backup["tracks"]) == len(pl.tracks)
            assert all(isinstance(track, str) for track in pl_backup["tracks"])

        assert len(backup["tracks"]) == len(model.tracks)
        assert all(isinstance(track, str) for track in backup["tracks"])

        assert len(backup["albums"]) == len(model.albums)
        assert all(isinstance(album, str) for album in backup["albums"])

        assert len(backup["artists"]) == len(model.artists)
        assert all(isinstance(artist, str) for artist in backup["artists"])


class TestRemoteMutableLibrary(BaseModelTester):
    class MockRemoteMutableLibrary(RemoteMutableLibrary):
        source: ClassVar[str] = MockRemoteLibrary.source

    @pytest.fixture
    def api(self) -> RemoteAPI:
        return MockRemoteAPI()

    @pytest.fixture
    def model(self, api: RemoteAPI) -> RemoteMutableLibrary:
        return self.MockRemoteMutableLibrary(api=api)

    @pytest.fixture
    def playlists(self, playlists: list[Playlist], user: RemoteUser, faker: Faker) -> list[RemotePlaylist]:
        return [
            RemoteMutablePlaylist(
                **pl.model_dump(),
                owner=RemoteUser(name=faker.name(), uri=SimpleURI.from_id(faker.pystr(22, 22), kind=RemoteUser.type)),
                cursor=MockUrlCursor(url=faker.url())
            )
            for pl in playlists
        ]

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
            patch.object(RemoteMutablePlaylist, "sync") as mock_sync,
        ):
            results = await model.sync_playlists()
            assert len(results) == len(playlists)

            assert mock_get.call_count == len(playlists)
            assert mock_sync.call_count == len(playlists)

            assert len(model.log_sync_playlists(results, skip_log=True)) == len(playlists)
