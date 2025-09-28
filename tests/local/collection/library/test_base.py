import os
from pathlib import Path
from random import choice, sample
from typing import get_args, Generator
from unittest import mock
from unittest.mock import Mock

import pytest
from faker import Faker
from pydantic import TypeAdapter

from musify.local.collection.library._base import LocalLibrary
from musify.local.collection.playlist import LocalPlaylist, LocalPlaylistType
from musify.local.item.album import LocalAlbum
from musify.local.item.artist import LocalArtist
from musify.local.item.genre import LocalGenre
from musify.local.item.track import LocalTrack
from musify.models.collection.playlist import Playlist
from musify.processors_new.filters import ValuesFilter
from musify.utils import get_discriminator_values
from tests.models.testers import MusifyResourceTester
from tests.utils import GENRES


class TestLocalLibrary(MusifyResourceTester):
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
            library_folders: list[Path],
            track_folders: list[Path],
            faker: Faker
    ) -> list[LocalTrack]:
        """The tracks available in all library folders"""
        artists = [LocalArtist(name=f"artist {i+1}") for i in range(faker.random_int(10, 20))]
        albums = [LocalAlbum(name=f"album {i+1}") for i in range(faker.random_int(2, 5))]
        genres = [LocalGenre(name=genre) for genre in sample(GENRES, k=faker.random_int(10, 20))]

        for track in tracks:
            track.path = choice(library_folders).joinpath(choice(track_folders)).joinpath(track.path.name)
            track.path.parent.mkdir(parents=True, exist_ok=True)
            track.path.touch()

            track.artists = sample(artists, k=faker.random_int(1, 5))
            track.album = choice(albums)
            track.genres = sample(genres, k=faker.random_int(1, 5))

        return tracks

    @pytest.fixture
    def mock_load_track(self, tracks: list[LocalTrack]) -> Generator[mock.MagicMock, None, None]:
        """Mock LocalLibrary.load_track to return the provided tracks"""
        tracks_mapped = {track.path: track for track in tracks}

        async def _load_track(path: Path) -> LocalTrack:
            return tracks_mapped[path]

        with mock.patch.object(LocalLibrary, "load_track", side_effect=_load_track) as mock_load:
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
        extensions = tuple(get_discriminator_values(LocalPlaylistType))

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

            playlist = TypeAdapter(LocalPlaylistType).validate_python(dict(path=path, format=path.suffix.lstrip(".")))
            playlist.path.parent.mkdir(parents=True, exist_ok=True)
            playlist.path.touch()

            playlists.append(playlist)

        return playlists

    @pytest.fixture
    def mock_load_playlist(self, playlists: list[LocalPlaylist]) -> Generator[mock.MagicMock, None, None]:
        """Mock LocalLibrary.load_playlist to return the provided tracks"""
        pl_mapped = {pl.path: pl for pl in playlists}

        async def _load_playlist(path: Path) -> LocalPlaylist:
            return pl_mapped[path]

        with mock.patch.object(LocalLibrary, "load_playlist", side_effect=_load_playlist) as mock_load:
            yield mock_load

    @pytest.fixture
    def model(
            self,
            tracks: list[LocalTrack],
            library_folders: list[Path],
            playlist_folder: Path,
            faker: Faker
    ) -> LocalLibrary:
        return LocalLibrary(library_folders=library_folders, playlist_folder=playlist_folder)

    def test_convert_playlist_names_to_filter(self, model: LocalLibrary, playlists: list[Playlist]) -> None:
        names = {pl.name for pl in playlists}

        model.playlist_filter = names
        assert isinstance(model.playlist_filter, ValuesFilter)
        assert model.playlist_filter.values == names

    def test_gets_all_track_paths(self, model: LocalLibrary, tracks: list[LocalTrack]) -> None:
        expected = {track.path for track in tracks}
        assert expected
        assert set(model._iter_track_paths()) == expected

    def test_gets_all_playlist_paths(self, model: LocalLibrary, playlists: list[LocalPlaylist]) -> None:
        expected = {pl.path for pl in playlists}
        assert expected
        assert set(model._iter_playlist_paths()) == expected

    def test_gets_filtered_playlist_paths(self, model: LocalLibrary, playlists: list[LocalPlaylist]) -> None:
        all_playlist_names = [pl.name for pl in playlists]
        names = set([pl.name for pl in playlists][:len(playlists) // 2])
        assert names != all_playlist_names

        model.playlist_filter = ValuesFilter(values=names)
        assert {path.stem for path in model._iter_playlist_paths()} == names

    @staticmethod
    def assert_tracks_loaded(model: LocalLibrary, tracks: list[LocalTrack], mock_load: mock.MagicMock) -> None:
        """Assert that the given tracks were loaded into the model"""
        assert mock_load.call_count == len(tracks)
        mock_load.assert_has_calls([mock.call(track.path) for track in tracks], any_order=True)
        assert sorted(model.tracks, key=lambda x: x.path) == sorted(tracks, key=lambda x: x.path)

    @staticmethod
    def assert_playlists_loaded(model: LocalLibrary, playlists: list[Playlist], mock_load: mock.MagicMock) -> None:
        """Assert that the given playlists were loaded into the model"""
        assert mock_load.call_count == len(playlists)
        mock_load.assert_has_calls([mock.call(pl.path) for pl in playlists], any_order=True)
        assert model.playlists == {pl.name: pl for pl in playlists}

    async def test_load(
            self,
            model: LocalLibrary,
            tracks: list[LocalTrack],
            mock_load_track: mock.MagicMock,
            playlists: list[LocalPlaylist],
            mock_load_playlist: mock.MagicMock
    ) -> None:
        await model.load()
        self.assert_tracks_loaded(model, tracks, mock_load_track)
        self.assert_playlists_loaded(model, playlists, mock_load_playlist)

    ###########################################################################
    ## Tracks
    ###########################################################################
    async def test_load_track_logs_error_safely(self, model: LocalLibrary, faker: Faker) -> None:
        path = faker.file_path(extension="m3u")
        await model.load_track(path)
        assert model.errors == [path]

    async def test_load_tracks(
            self, model: LocalLibrary, tracks: list[LocalTrack], mock_load_track: mock.MagicMock,
    ) -> None:
        for track in tracks[:10]:  # ensure these tracks preloaded tracks are replaced
            model.tracks.append(track)
            os.remove(track.path)

        await model.load_tracks()
        self.assert_tracks_loaded(model, tracks[10:], mock_load_track)

    def test_log_tracks(self, model: LocalLibrary, tracks: list[LocalTrack]) -> None:
        model.tracks[:] = tracks
        print(model.log_tracks())
        assert len(model.log_tracks().split("\n")) == 1  # just summarises

    ###########################################################################
    ## Playlists
    ###########################################################################
    async def test_load_playlist_logs_error_safely(self, model: LocalLibrary, faker: Faker) -> None:
        path = faker.file_path(extension="mp3")
        await model.load_playlist(path)
        assert model.errors == [path]

    async def test_load_playlists(
            self, model: LocalLibrary, playlists: list[LocalPlaylist], mock_load_playlist: mock.MagicMock,
    ) -> None:
        for pl in playlists[:5]:  # ensure these tracks preloaded playlists are replaced
            model.playlists[pl.name] = pl
            os.remove(pl.path)

        await model.load_playlists()
        self.assert_playlists_loaded(model, playlists[5:], mock_load_playlist)

    def test_log_playlists(self, model: LocalLibrary, playlists: list[LocalPlaylist]) -> None:
        model.playlists.update({pl.name: pl for pl in playlists}, extract_keys=False)
        print(model.log_playlists())
        assert len(model.log_playlists().split("\n")) == len(playlists) + 1  # +1 for the header

    async def test_save_playlists(self, model: LocalLibrary, playlists: list[LocalPlaylist]) -> None:
        model.playlists.update({pl.name: pl for pl in playlists}, extract_keys=False)
        results = await model.save_playlists(dry_run=True)
        assert results.keys() == model.playlists.keys()

    ###########################################################################
    ## Collections
    ###########################################################################
    def test_collections(self, model: LocalLibrary, tracks: list[LocalTrack], track_folders: list[Path]) -> None:
        model.tracks[:] = tracks

        assert len(list(model.folders())) == len(set(track_folders)) > 0
        assert len(list(model.albums())) == len(set(track.album.name for track in model.tracks)) > 0

        expected_artists = len(set(artist.name for track in model.tracks for artist in track.artists))
        assert len(list(model.artists())) == expected_artists > 0

        expected_genres = len(set(genre.name for track in model.tracks for genre in track.genres))
        assert len(list(model.genres())) == expected_genres > 0
