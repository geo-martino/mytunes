from copy import deepcopy
from pathlib import Path
from typing import Any, Generator
from unittest import mock

import pytest
from faker import Faker

from musify.local.collection.playlist.m3u import M3U, SyncResultM3U
from musify.local.item.track import LocalTrack
from musify.models.properties.file import PathMapper, PathStemMapper
from tests.models.testers import UniqueKeyTester


class TestM3UResult:
    def test_from_paths(self, faker: Faker):
        paths_initial = [Path(faker.file_path()) for _ in range(10)]
        paths_final = paths_initial[:5] + [Path(faker.file_path()) for _ in range(7)]

        result = SyncResultM3U.from_paths(paths_initial, paths_final)

        assert result.start == len(paths_initial)
        assert result.added == 7
        assert result.removed == 5
        assert result.unchanged == 5
        assert result.difference == 2
        assert result.final == len(paths_final)


class TestM3U(UniqueKeyTester):

    @pytest.fixture
    async def model(self, tracks: list[LocalTrack], faker: Faker, tmp_path: Path) -> M3U:
        playlist = M3U(path=tmp_path.joinpath(faker.file_path(absolute=False, extension="m3u")))
        return await playlist.load(tracks=tracks)

    @pytest.fixture
    def path_mapper(self, tracks: list[LocalTrack]) -> PathStemMapper:
        stem_map = {parent: Path(parent.parent, "folder") for parent in set(track.path.parent for track in tracks)}
        return PathStemMapper(stem_map=stem_map)

    @pytest.fixture
    def path(self, tracks_on_disk: list[LocalTrack], path_mapper: PathMapper, faker: Faker, tmp_path: Path) -> Path:
        path = tmp_path.joinpath(faker.file_name(extension="m3u"))
        path.parent.mkdir(parents=True, exist_ok=True)

        track_paths = path_mapper.unmap_many(tracks_on_disk, check_existence=False)
        with path.open("w", encoding="utf-8") as file:
            file.writelines((f"{path}\n" for path in track_paths))

        return path

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

        def _from_path(path: str | Path) -> LocalTrack:
            return next(tr for tr in tracks if tr.path == path)

        with mock.patch.object(LocalTrack, "from_path", side_effect=_from_path):
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

    async def test_load_from_empty_file(
            self, tracks: list[LocalTrack], faker: Faker, tmp_path: Path
    ):
        path = tmp_path.joinpath(faker.file_path(absolute=False, extension="m3u"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
        pl = M3U(path=path)

        # playlist file is empty so no tracks should be loaded or updated
        # to add tracks to the playlist, use pl.tracks.extend(tracks) and then save
        await pl.load(tracks)
        assert not pl.tracks
        assert not pl._original

    async def test_load_from_no_file(
            self,
            tracks_on_disk: list[LocalTrack],
            tracks_in_memory: list[LocalTrack],
            faker: Faker,
            tmp_path: Path,
    ):
        path = tmp_path.joinpath(faker.file_path(absolute=False, extension="m3u"))
        pl = M3U(path=path)
        assert len(pl.tracks) == 0

        # no playlist file exists so tracks are loaded from the given tracks
        await pl.load(tracks_on_disk)
        assert pl.tracks == tracks_on_disk
        assert not pl._original

        # tracks are added even if they don't exist on disk
        await pl.load(tracks_on_disk + tracks_in_memory)
        assert pl.tracks == tracks_on_disk + tracks_in_memory
        assert not pl._original

    # noinspection PyTestUnpassedFixture
    async def test_load_from_file_with_no_given_tracks(
            self,
            path: Path,
            path_mapper: PathMapper,
            tracks_on_disk: list[LocalTrack],
            tracks_in_memory: list[LocalTrack]
    ):
        # add tracks that don't exist on disk to playlist file
        with path.open("a", encoding="utf-8") as file:
            file.writelines((f"{track.path}\n" for track in tracks_in_memory))

        pl = M3U(path=path, path_mapper=path_mapper)

        # only loads tracks that exist on disk
        await pl.load()
        assert pl.tracks == tracks_on_disk

        # reloads only with given tracks
        await pl.load(tracks_on_disk[:2] + tracks_in_memory)
        assert pl.tracks == tracks_on_disk[:2]

        # ...and then reloads all tracks from disk that match conditions when no tracks are given
        await pl.load()
        assert pl.tracks == tracks_on_disk

    async def test_load_from_file_with_given_tracks(
            self,
            path: Path,
            path_mapper: PathMapper,
            tracks_on_disk: list[LocalTrack],
            tracks_in_memory: list[LocalTrack]
    ):
        pl = M3U(path=path, path_mapper=path_mapper)

        # given tracks aren't in the playlist file so no tracks are loaded
        await pl.load(tracks_in_memory)
        assert not pl.tracks

        # reloads only with given tracks that are in playlist
        await pl.load(tracks_on_disk[:2])
        assert pl.tracks == tracks_on_disk[:2]

        # reloads only tracks that exist on disk
        await pl.load(tracks_on_disk + tracks_in_memory)
        assert pl.tracks == tracks_on_disk

    async def test_save_file_dry_run(self, tracks: list[LocalTrack], faker: Faker, tmp_path: Path):
        path = tmp_path.joinpath(faker.file_path(absolute=False, extension="m3u"))

        pl = M3U(path=path)
        pl.tracks.extend(tracks)

        await pl.save(dry_run=True)

        assert not path.exists()
        assert pl.modified_at is None
        assert pl.created_at is None

    async def test_save_to_new_file(
            self,
            tracks: list[LocalTrack],
            tracks_on_disk: list[LocalTrack],
            tracks_in_memory: list[LocalTrack],
            path_mapper: PathMapper,
            faker: Faker,
            tmp_path: Path,
    ):
        path = tmp_path.joinpath(faker.file_path(absolute=False, extension="m3u"))

        pl = M3U(path=path, path_mapper=path_mapper)
        await pl.load(tracks=tracks_on_disk)

        assert not pl.path.is_file()
        assert pl.modified_at is None
        assert pl.created_at is None

        result = await pl.save(dry_run=False)

        assert path.is_file()
        assert pl.modified_at is not None
        assert pl.created_at is not None

        with open(path, "r") as file:
            paths = [line.strip() for line in file]

        assert len(paths) == result.final
        assert paths != [track.path for track in pl.tracks]
        assert paths == [path_mapper.unmap(track.path) for track in pl.tracks]

    async def test_save_to_existing_file(
            self,
            path: Path,
            tracks: list[LocalTrack],
            tracks_on_disk: list[LocalTrack],
            tracks_in_memory: list[LocalTrack],
            path_mapper: PathMapper,
            faker: Faker,
            tmp_path: Path,
    ):
        # add tracks that don't exist on disk to playlist file to check that remapping happens
        with path.open("a", encoding="utf-8") as file:
            file.writelines((f"{path_mapper.unmap(track.path, check_existence=False)}\n" for track in tracks_in_memory))

        pl = M3U(path=path, path_mapper=path_mapper)
        await pl.load(tracks_on_disk + tracks_in_memory[:2])

        assert pl.path.is_file()
        original_dt_modified = pl.modified_at
        # original_dt_created = pl.created_at

        result = await pl.save(dry_run=False)

        # TODO: these assertions fail on GitHub actions but not locally, why?
        assert pl.modified_at > original_dt_modified
        # assert pl.created_at == original_dt_created  # doesn't work

        with open(path, "r") as file:
            paths = [line.strip() for line in file]

        assert len(paths) == result.final
        assert paths != [track.path for track in pl.tracks]
        assert paths == [path_mapper.unmap(track.path) for track in pl.tracks]

    async def test_save_to_new_file_from_existing(
            self,
            path: Path,
            tracks_on_disk: list[LocalTrack],
            path_mapper: PathMapper,
            faker: Faker,
            tmp_path: Path,
    ):
        pl = M3U(path=path, path_mapper=path_mapper)
        pl.tracks.extend(tracks_on_disk)

        assert pl.path.is_file()
        assert pl.modified_at is not None
        assert pl.created_at is not None

        pl.name = "New Playlist"
        assert pl.path == path
        assert path.is_file()
        assert pl.modified_at is not None
        assert pl.created_at is not None

        await pl.save(dry_run=False)

        assert pl.path == path.with_stem("New Playlist")
        assert not path.is_file()
        assert pl.path.is_file()
        assert pl.modified_at is not None
        assert pl.created_at is not None
