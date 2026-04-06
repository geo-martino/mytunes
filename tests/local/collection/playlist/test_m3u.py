from collections.abc import Generator
from copy import deepcopy
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from faker import Faker

from musify.local._collection.playlist.m3u import M3U, SyncM3UResult
from musify.local._item.track import LocalTrack
from musify.models.properties.file import PathMapper
from tests.local.collection.playlist.testers import LocalPlaylistTester
from tests.models.testers import BaseModelTester


class TestSyncM3UResult(BaseModelTester):
    @pytest.fixture
    def model(self, faker: Faker) -> SyncM3UResult:
        return SyncM3UResult(
            start=faker.random_int(0, 100),
            added=faker.random_int(0, 100),
            removed=faker.random_int(0, 100),
            unchanged=faker.random_int(0, 100),
            difference=faker.random_int(-100, 100),
            final=faker.random_int(0, 100),
        )

    def test_from_paths(self, faker: Faker):
        paths_initial = [Path(faker.file_path()) for _ in range(10)]
        paths_final = paths_initial[:5] + [Path(faker.file_path()) for _ in range(7)]

        result = SyncM3UResult.from_paths(paths_initial, paths_final)

        assert result.start == len(paths_initial)
        assert result.added == 7
        assert result.removed == 5
        assert result.unchanged == 5
        assert result.difference == 2
        assert result.final == len(paths_final)


class TestM3U(LocalPlaylistTester):

    @pytest.fixture
    async def model(self, path_mapper: PathMapper, faker: Faker, tmp_path: Path) -> M3U:
        path = tmp_path.joinpath(faker.file_path(absolute=False, extension="m3u"))
        playlist = M3U(path=path, path_mapper=path_mapper)
        await playlist.load()
        return playlist

    @pytest.fixture
    def path(self, model: M3U, tracks_on_disk: list[LocalTrack], path_mapper: PathMapper) -> Path:
        """Creates an actual playlist file with some tracks on disk."""
        track_paths = path_mapper.unmap_many(tracks_on_disk, check_existence=False)

        model.path.parent.mkdir(parents=True, exist_ok=True)
        with model.path.open("w", encoding="utf-8") as file:
            file.writelines((f"{path_mapper.unmap(path, check_existence=False)}\n" for path in track_paths))

        return model.path

    @pytest.fixture
    def tracks_on_disk(
            self, tracks: list[LocalTrack], path_mapper: PathMapper
    ) -> Generator[list[LocalTrack], Any, None]:
        """Creates mock loaders for a subset of tracks"""
        tracks = deepcopy(tracks[:len(tracks) // 3])
        for track in tracks:
            track.path = Path(path_mapper.map(track.path, check_existence=False))
            track.path.parent.mkdir(parents=True, exist_ok=True)
            track.path.touch(exist_ok=True)

        def _load_track(path: str | Path) -> LocalTrack:
            return next(tr for tr in tracks if tr.path == Path(path_mapper.map(path)))

        with patch.object(M3U, "_load_track", side_effect=_load_track):
            yield tracks

    @pytest.fixture
    def tracks_in_memory(
            self,
            tracks: list[LocalTrack],
            tracks_on_disk: list[LocalTrack],
            path_mapper: PathMapper
    ) -> list[LocalTrack]:
        """Yield list of tracks where some are present in the test playlist and some are not"""
        tracks_on_disk_names = {track.name for track in tracks_on_disk}
        tracks = [track for track in deepcopy(tracks) if track.name not in tracks_on_disk_names]

        for track in tracks:
            track.path = Path(path_mapper.map(track.path, check_existence=False))

        return tracks

    async def test_load_from_empty_file(self, model: M3U, tracks: list[LocalTrack]):
        model.path.parent.mkdir(parents=True, exist_ok=True)
        model.path.touch(exist_ok=True)

        await model.load(tracks)
        assert not model.tracks
        assert not model._original

    async def test_load_from_no_file(
            self, model: M3U, tracks_on_disk: list[LocalTrack], tracks_in_memory: list[LocalTrack],
    ):
        assert len(model.tracks) == 0

        # no playlist file exists so tracks are loaded from the given tracks
        await model.load(tracks_on_disk)
        assert model.tracks == tracks_on_disk
        assert not model._original

        # tracks are added even if they don't exist on disk
        await model.load(tracks_on_disk + tracks_in_memory)
        assert model.tracks == tracks_on_disk + tracks_in_memory
        assert not model._original

    async def test_load_from_file_with_no_given_tracks(
            self, model: M3U, path: Path, tracks_on_disk: list[LocalTrack], tracks_in_memory: list[LocalTrack]
    ):
        # only loads tracks that exist on disk
        model = M3U(path=path, path_mapper=model.path_mapper)
        await model.load()
        assert model.tracks == tracks_on_disk

        # reloads only with given tracks
        await model.load(tracks_on_disk[:2] + tracks_in_memory)
        assert model.tracks == tracks_on_disk[:2]

        # ...and then reloads all tracks from disk that match conditions when no tracks are given
        await model.load()
        assert model.tracks == tracks_on_disk

    async def test_load_from_file_with_given_tracks(
            self, model: M3U, path: Path, tracks_on_disk: list[LocalTrack], tracks_in_memory: list[LocalTrack]
    ):
        # given tracks aren't in the playlist file so no tracks are loaded
        await model.load(tracks_in_memory)
        assert not model.tracks

        # reloads only with given tracks that are in playlist
        await model.load(tracks_on_disk[:2])
        assert model.tracks == tracks_on_disk[:2]

        # reloads only tracks that exist on disk
        await model.load(tracks_on_disk + tracks_in_memory)
        assert model.tracks == tracks_on_disk

    def assert_saved_file(self, model: M3U) -> None:
        """Asserts that the saved playlist file contains the correct mapped paths."""
        with open(model.path, "r") as file:
            paths = [line.strip() for line in file]

        assert paths != [track.path for track in model.tracks]
        assert paths == [model.path_mapper.unmap(track.path) for track in model.tracks]
        self.assert_paths_are_mapped(paths)

    async def test_save_dry_run(self, model: M3U, tracks: list[LocalTrack]):
        model.tracks.replace(tracks)
        await self.assert_save_dry_run(model)

    async def test_save_to_new_file(
            self, model: M3U, tracks_on_disk: list[LocalTrack], tracks_in_memory: list[LocalTrack]
    ):
        await model.load(tracks=tracks_on_disk)
        assert await model.save(dry_run=True) == await self.assert_save(model)
        self.assert_saved_file(model)

    async def test_save_to_existing_file(
            self, model: M3U, path: Path, tracks_on_disk: list[LocalTrack], tracks_in_memory: list[LocalTrack],
    ):
        # add tracks that don't exist on disk to playlist file to check that remapping happens
        with path.open("a", encoding="utf-8") as file:
            file.writelines(
                (f"{model.path_mapper.unmap(track.path, check_existence=False)}\n" for track in tracks_in_memory)
            )

        await model.load(tracks_on_disk + tracks_in_memory[:2])
        await self.assert_save_to_existing_file(model)
        self.assert_saved_file(model)

    async def test_save_to_new_file_from_existing(self, model: M3U, path: Path, tracks_on_disk: list[LocalTrack]):
        model.tracks.replace(tracks_on_disk)
        await self.assert_save_to_new_file(model, path)
