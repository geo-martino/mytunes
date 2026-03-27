from collections.abc import Iterable
from copy import deepcopy
from pathlib import Path
from random import randrange, sample

import pytest

from musify.base import MusifyItem
from musify.file.path_mapper import PathMapper, PathStemMapper
from musify.libraries.local.library import LocalLibrary
from musify.libraries.local.playlist import PLAYLIST_CLASSES, LocalPlaylist
from musify.libraries.local.track import LocalTrack
from musify.processors.filter import FilterDefinedList, FilterIncludeExclude
from tests.libraries.local.library.testers import LocalLibraryTester
from tests.libraries.local.track.utils import random_track, random_tracks
from tests.libraries.local.utils import path_playlist_m3u, path_playlist_xautopf_bp
from tests.libraries.local.utils import path_playlist_resources, path_playlist_all
from tests.libraries.local.utils import path_track_resources, path_track_all
from tests.utils import path_resources


class TestLocalLibrary(LocalLibraryTester):

    @pytest.fixture
    async def library(self) -> LocalLibrary:
        library = LocalLibrary(library_folders=path_resources, playlist_folder=path_playlist_resources)
        await library.load()

        # needed to ensure __setitem__ check passes
        library.items.append(random_track(cls=library[0].__class__))
        return library

    @pytest.fixture
    def collection_merge_items(self) -> Iterable[LocalTrack]:
        return random_tracks(randrange(5, 10))

    def test_library(self) -> None:
        library = LocalLibrary()
        assert not library.library_folders
        assert len(library._track_paths) == 0

        library.library_folders = path_track_resources
        assert library.library_folders == [path_track_resources]
        assert library._track_paths == path_track_all

        assert library.playlist_folder is None
        assert not library._playlist_paths

        library.playlist_folder = path_playlist_resources
        assert library.playlist_folder == path_playlist_resources
        assert library._playlist_paths == {path.stem: path for path in path_playlist_all}

    def test_init_include(self):
        library = LocalLibrary(
            library_folders=path_track_resources,
            playlist_folder=path_playlist_resources,
            playlist_filter=FilterDefinedList([path_playlist_m3u.stem, path_playlist_xautopf_bp.stem]),
        )
        assert library.library_folders == [path_track_resources]
        assert library._track_paths == path_track_all
        assert library.playlist_folder == path_playlist_resources

        expected_playlists = {
            pl.stem: pl for pl in [path_playlist_m3u, path_playlist_xautopf_bp]
            if any(pl.suffix == ext for cls in PLAYLIST_CLASSES for ext in cls.valid_extensions)
        }
        assert library._playlist_paths == expected_playlists

    def test_init_exclude(self, path_mapper: PathStemMapper):
        library = LocalLibrary(
            library_folders=path_track_resources,
            playlist_folder=path_playlist_resources,
            playlist_filter=FilterIncludeExclude(
                include=FilterDefinedList(),
                exclude=FilterDefinedList([path_playlist_xautopf_bp.stem])
            ),
            path_mapper=path_mapper,
        )

        assert set(path_mapper.available_paths.values()) == set(map(str, library._track_paths))

        assert library.playlist_folder == path_playlist_resources
        assert library._playlist_paths == {
            path.stem: path for path in path_playlist_all if path != path_playlist_xautopf_bp
        }

    def test_init_relative_paths(self):
        library_relative_paths = LocalLibrary(
            library_folders=path_resources, playlist_folder=path_playlist_resources.name,
        )
        assert len(library_relative_paths._track_paths) == 6
        assert library_relative_paths.playlist_folder == path_playlist_resources
        assert library_relative_paths._playlist_paths == {
            path.stem: path for path in path_playlist_all
        }

    def test_collection_creators(self, library: LocalLibrary):
        assert len(library.folders) == len(set(track.folder for track in library.tracks))
        assert len(library.albums) == len(set(track.album for track in library.tracks))
        assert len(library.artists) == len(set(artist for track in library.tracks for artist in track.artists))
        assert len(library.genres) == len(set(genre for track in library.tracks for genre in track.genres))

    async def test_load(self, path_mapper: PathMapper):
        library = LocalLibrary(
            library_folders=path_track_resources, playlist_folder=path_playlist_resources, path_mapper=path_mapper
        )
        await library.load()
        tracks = {track.path for track in library.tracks}
        playlists = {name: pl.path for name, pl in library.playlists.items()}

        assert tracks == library._track_paths == path_track_all
        assert playlists == {path.stem: path for path in path_playlist_all}
        assert all(pl.path_mapper == path_mapper for pl in library.playlists.values())

        assert library.last_played is None
        assert library.last_added is None
        assert library.last_modified == max(track.date_modified for track in library.tracks)

        library.library_folders = [path_track_resources, path_playlist_resources]
        await library.load()

        assert len(library.tracks) == len(library._track_paths) == len(path_track_all) + 2

    @pytest.fixture
    def merge_playlists_updated_paths(
            self, library: LocalLibrary, collection_merge_items: Iterable[MusifyItem], tmp_path: Path
    ) -> list[LocalPlaylist]:
        """Set of new playlists with updated paths to merge with the given ``library``"""
        playlists = sample(list(library.playlists.values()), k=2)
        for pl in playlists:
            pl.path = tmp_path.joinpath("path/to/playlists").joinpath(pl.path.name)
            library.playlists.pop(pl.name)

        assert all(pl.name not in library.playlists for pl in playlists)
        return playlists

    def test_merge_playlists_updates_no_parent(
            self, library: LocalLibrary, merge_playlists_updated_paths: list[LocalPlaylist]
    ):
        # paths update using just filename
        self.assert_merge_playlists(
            library, test=merge_playlists_updated_paths, new_playlists=merge_playlists_updated_paths
        )

        for pl in merge_playlists_updated_paths:
            assert not str(pl.path).startswith(str(library.playlist_folder))  # did not modify original playlist

            pl_lib = library.playlists[pl.name]
            assert str(pl_lib.path).startswith(str(library.playlist_folder))
            assert str(pl_lib.path.relative_to(library.playlist_folder)) == pl.path.name

    def test_merge_playlists_updates_with_parent(
            self, library: LocalLibrary, merge_playlists_updated_paths: list[LocalPlaylist], tmp_path: Path
    ):
        # paths updated replacing on library stem path
        test = deepcopy(library)
        test.playlists.clear()
        test.playlists.update({pl.name: pl for pl in merge_playlists_updated_paths})
        test.playlist_folder = tmp_path
        assert library.playlist_folder != test.playlist_folder

        self.assert_merge_playlists(library=library, test=test, new_playlists=merge_playlists_updated_paths)

        for pl in merge_playlists_updated_paths:
            assert not str(pl.path).startswith(str(library.playlist_folder))  # did not modify original playlist

            pl_lib = library.playlists[pl.name]
            assert str(pl_lib.path).startswith(str(library.playlist_folder))
            assert str(pl_lib.path.relative_to(library.playlist_folder)) != pl.path.name
            assert pl_lib.path.relative_to(library.playlist_folder) == pl.path.relative_to(tmp_path)
