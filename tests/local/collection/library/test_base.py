import os
from asyncio import Semaphore
from collections.abc import Generator
from pathlib import Path
from random import choice, sample
from unittest import mock
from unittest.mock import patch, Mock

import pytest
from faker import Faker
from pydantic import TypeAdapter
from pytest_mock import MockerFixture

from musify.local.collection.library import LocalLibrary
from musify.local.collection.playlist import LocalPlaylist
from musify.local.item.album import LocalAlbum
from musify.local.item.artist import LocalArtist
from musify.local.item.genre import LocalGenre
from musify.local.item.track import LocalTrack
from musify.models.collection.playlist import Playlist
from musify.processors.filters.values import ValueFilter, NameFilter
from tests.models.testers import NoUniqueKeyTester


class TestLocalLibrary(NoUniqueKeyTester):
    @pytest.fixture
    def library_folders(self, faker: Faker, tmp_path: Path) -> list[Path]:
        """The folders which contain library tracks and playlists."""
        return [tmp_path.joinpath(faker.sentence()) for _ in range(faker.random_int(1, 4))]

    @pytest.fixture
    def playlist_folder(self, faker: Faker) -> Path:
        """The relative path to a playlist folder found within the library folders"""
        return Path(faker.file_path(depth=faker.random_int(2, 5), absolute=False)).parent

    @pytest.fixture
    def track_folders(self, faker: Faker) -> list[Path]:
        """The relative paths to all tracks in the library folders"""
        return [
            Path(faker.file_path(depth=faker.random_int(2, 5), absolute=False)).parent
            for _ in range(faker.random_int(3, 5))
        ]

    @pytest.fixture
    def tracks(
            self,
            tracks: list[LocalTrack],
            artists: list[LocalArtist],
            albums: list[LocalAlbum],
            genres: list[LocalGenre],
            library_folders: list[Path],
            track_folders: list[Path],
            faker: Faker
    ) -> list[LocalTrack]:
        """The tracks available in all library folders"""
        for track in tracks:
            track.path = choice(library_folders).joinpath(choice(track_folders)).joinpath(track.path.name)
            track.path.parent.mkdir(parents=True, exist_ok=True)
            track.path.touch()

            track.artists = sample(artists, k=faker.random_int(1, 5))
            track.album = choice(albums)
            track.album.artists.extend(track.artists)
            track.genres = sample(genres, k=faker.random_int(1, 5))

        return tracks

    @pytest.fixture
    def mock_load_track(self, tracks: list[LocalTrack]) -> Generator[Mock, None, None]:
        """Mock LocalLibrary.load_track to return the provided tracks"""
        tracks_mapped = {track.path: track for track in tracks}

        async def _load_track(path: Path) -> LocalTrack:
            return tracks_mapped[path]

        with patch.object(LocalLibrary, "load_track", side_effect=_load_track) as mock_load:
            yield mock_load

    @pytest.fixture
    def playlists(
            self,
            library_folders: list[Path],
            playlist_folder: Path,
            faker: Faker,
    ) -> list[LocalPlaylist]:
        """The tracks available in all library folders"""
        playlists = []
        extensions = tuple(LocalPlaylist.supported_extensions)

        adapter = TypeAdapter(LocalPlaylist.annotation)

        for _ in range(faker.random_int(10, 20)):
            # need to ensure unique names for tests to work as expected
            path_relative: Path | None = None
            while path_relative is None or any(path_relative.stem == pl.name for pl in playlists):
                path_relative = Path(faker.file_path(
                    depth=faker.random_int(0, 2),
                    absolute=False,
                    extension=choice(extensions)
                ))
            path = choice(library_folders).joinpath(playlist_folder).joinpath(path_relative)

            playlist = adapter.validate_python(dict(path=path))
            playlist.path.parent.mkdir(parents=True, exist_ok=True)
            playlist.path.touch()

            playlists.append(playlist)

        return playlists

    @pytest.fixture
    def mock_load_playlist(self, playlists: list[LocalPlaylist]) -> Generator[Mock, None, None]:
        """Mock LocalLibrary.load_playlist to return the provided tracks"""
        pl_mapped = {pl.path: pl for pl in playlists}

        async def _load_playlist(path: Path) -> LocalPlaylist:
            return pl_mapped[path]

        with patch.object(LocalLibrary, "load_playlist", side_effect=_load_playlist) as mock_load:
            yield mock_load

    @pytest.fixture
    def mock_semaphore(self, mocker: MockerFixture) -> Mock:
        return mocker.spy(Semaphore, "acquire")

    @pytest.fixture
    def model(
            self,
            tracks: list[LocalTrack],
            library_folders: list[Path],
            playlist_folder: Path,
            faker: Faker
    ) -> LocalLibrary:
        return LocalLibrary(library_folders=library_folders, playlist_folder=playlist_folder)

    def test_convert_playlist_names_to_filter(self, model: LocalLibrary, playlists: list[Playlist]):
        names = {pl.name for pl in playlists}

        model.playlist_filter = NameFilter(values=names)
        assert isinstance(model.playlist_filter, NameFilter)
        assert model.playlist_filter.values == names

    def test_gets_all_track_paths(self, model: LocalLibrary, tracks: list[LocalTrack]):
        expected = {track.path for track in tracks}
        assert expected
        assert set(model._track_paths) == expected

    def test_gets_all_playlist_paths(self, model: LocalLibrary, playlists: list[LocalPlaylist]):
        expected = {pl.path for pl in playlists}
        assert expected
        assert set(model._playlist_paths) == expected

    def test_gets_filtered_playlist_paths(self, model: LocalLibrary, playlists: list[LocalPlaylist]):
        all_playlist_names = [pl.name for pl in playlists]
        names = set([pl.name for pl in playlists][:len(playlists) // 2])
        assert names != all_playlist_names

        model.playlist_filter = NameFilter(values=names)
        assert {path.stem for path in model._playlist_paths} == names

    @staticmethod
    def assert_tracks_loaded(model: LocalLibrary, tracks: list[LocalTrack], mock_load: Mock) -> None:
        """Assert that the given tracks were loaded into the model"""
        paths = set(track.path for track in tracks)

        assert mock_load.call_count == len(paths)
        mock_load.assert_has_calls([mock.call(path) for path in paths], any_order=True)

        if len(model.tracks) == len(tracks):  # tracks are not always unique
            assert sorted(model.tracks, key=lambda x: x.path) == sorted(tracks, key=lambda x: x.path)

    @staticmethod
    def assert_playlists_loaded(model: LocalLibrary, playlists: list[LocalPlaylist], mock_load: Mock) -> None:
        """Assert that the given playlists were loaded into the model"""
        paths = set(pl.path for pl in playlists)

        assert mock_load.call_count == len(paths)
        mock_load.assert_has_calls([mock.call(path) for path in paths], any_order=True)

        assert sorted(model.playlists.unique, key=lambda pl: pl.name) == sorted(playlists, key=lambda pl: pl.name)

    async def test_load(
            self,
            model: LocalLibrary,
            tracks: list[LocalTrack],
            mock_load_track: Mock,
            playlists: list[LocalPlaylist],
            mock_load_playlist: Mock,
            mock_semaphore: Mock,
    ):
        await model.load()
        self.assert_tracks_loaded(model, tracks, mock_load_track)
        self.assert_playlists_loaded(model, playlists, mock_load_playlist)

    ###########################################################################
    ## Tracks
    ###########################################################################
    async def test_load_track(self, model: LocalLibrary, mock_semaphore: Mock, faker: Faker):
        path = faker.file_path(extension="m3u")

        await model.load_track(path)
        assert model.errors == [path]
        mock_semaphore.assert_called_once()

    async def test_load_tracks(
            self, model: LocalLibrary, tracks: list[LocalTrack], mock_load_track: Mock,
    ):
        for track in tracks[:10]:  # ensure these tracks preloaded tracks are replaced
            model.tracks.append(track)
            os.remove(track.path)

        await model.load_tracks()
        self.assert_tracks_loaded(model, tracks[10:], mock_load_track)

    ###########################################################################
    ## Playlists
    ###########################################################################
    async def test_load_playlist(self, model: LocalLibrary, mock_semaphore: Mock, faker: Faker):
        path = faker.file_path(extension="mp3")

        await model.load_playlist(path)
        assert model.errors == [path]
        mock_semaphore.assert_called_once()

    async def test_load_playlists(
            self, model: LocalLibrary, playlists: list[LocalPlaylist], mock_load_playlist: Mock,
    ):
        for pl in playlists[:5]:  # ensure these tracks preloaded playlists are replaced
            model.playlists[pl.name] = pl
            os.remove(pl.path)

        await model.load_playlists()
        self.assert_playlists_loaded(model, playlists[5:], mock_load_playlist)

    async def test_save_playlists(self, model: LocalLibrary, playlists: list[LocalPlaylist]):
        model.playlists.update(playlists)
        results = await model.save_playlists(dry_run=True)
        assert list(results.keys()) == [pl.name for pl in playlists]

    ###########################################################################
    ## Collections
    ###########################################################################
    def test_folders(self, model: LocalLibrary, tracks: list[LocalTrack], track_folders: list[Path]):
        model.tracks[:] = tracks

        folders = list(model.folders())
        assert len(folders) == len(set(track_folders)) > 0
        assert all(folder.count > 0 for folder in folders)

    def test_albums(self, model: LocalLibrary, tracks: list[LocalTrack], track_folders: list[Path]):
        model.tracks[:] = tracks

        albums = list(model.albums())
        assert len(albums) == len(set(track.album.name for track in model.tracks)) > 0
        assert all(album.count > 0 for album in albums)

    def test_artists(self, model: LocalLibrary, tracks: list[LocalTrack], track_folders: list[Path]):
        model.tracks[:] = tracks
        expected_artists = len(set(artist.name for track in model.tracks for artist in track.artists))

        artists = list(model.artists())
        assert len(artists) == expected_artists > 0
        assert all(artist.count > 0 for artist in artists)

    def test_genres(self, model: LocalLibrary, tracks: list[LocalTrack], track_folders: list[Path]):
        model.tracks[:] = tracks
        expected_genres = len(set(genre.name for track in model.tracks for genre in track.genres))

        genres = list(model.genres())
        assert len(genres) == expected_genres > 0
        assert all(genre.count > 0 for genre in genres)
