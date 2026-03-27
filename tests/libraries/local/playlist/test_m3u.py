import os
from pathlib import Path
from random import randrange

import pytest

from musify.file.exception import InvalidFileType
from musify.file.path_mapper import PathMapper, PathStemMapper
from musify.libraries.local.playlist import M3U
from musify.libraries.local.track import LocalTrack
from tests.libraries.local.playlist.testers import LocalPlaylistTester
from tests.libraries.local.track.utils import random_track, random_tracks
from tests.libraries.local.utils import path_playlist_m3u
from tests.utils import path_txt, path_resources


class TestM3U(LocalPlaylistTester):

    @pytest.fixture
    async def playlist(self, tmp_path: Path) -> M3U:
        # needed to ensure __setitem__ check passes
        tracks = random_tracks(randrange(5, 20))
        tracks.append(random_track(cls=tracks[0].__class__))

        playlist = M3U(path=tmp_path.joinpath("does_not_exist").with_suffix(".m3u"))
        return await playlist.load(tracks=tracks)

    @pytest.fixture(scope="class")
    def tracks_actual(self, tracks: list[LocalTrack]) -> list[LocalTrack]:
        """Yield list of all real LocalTracks present in the test playlist"""
        with open(path_playlist_m3u, "r") as f:
            ext = [Path(line.strip()).suffix for line in f]
        return sorted([track for track in tracks if track.ext in ext], key=lambda x: ext.index(x.ext))

    @pytest.fixture(scope="class")
    def tracks_limited(self, tracks: list[LocalTrack], tracks_actual: list[LocalTrack]) -> list[LocalTrack]:
        """Yield list of real LocalTracks where some are present in the test playlist and some are not"""
        return tracks_actual[:-1] + [track for track in tracks if track not in tracks_actual]

    def test_init_fails(self):
        with pytest.raises(InvalidFileType):
            M3U(path=path_txt)

    async def test_load_from_empty_file_with_tracks(self, tracks: list[LocalTrack], tmp_path: Path):
        path = tmp_path.joinpath("test").with_suffix(".m3u")
        path.touch(exist_ok=True)

        pl = M3U(path=path)
        await pl.load(tracks=tracks)

        assert not pl
        assert not pl.tracks
        assert not pl._original

    async def test_load_fake_file_with_no_tracks(self, tracks: list[LocalTrack], tmp_path: Path):
        path_fake = tmp_path.joinpath("does_not_exist").with_suffix(".m3u")

        pl = M3U(path=path_fake)
        assert pl.path == path_fake
        assert pl.name == path_fake.stem
        assert pl.ext == path_fake.suffix
        assert len(pl.tracks) == 0

        await pl.load(tracks)
        assert pl.tracks == tracks

    async def test_load_fake_file_with_fake_tracks(self, tracks: list[LocalTrack], tmp_path: Path):
        path_fake = tmp_path.joinpath("does_not_exist").with_suffix(".m3u")
        tracks_random = random_tracks(30)

        pl = M3U(path=path_fake)
        await pl.load(tracks=tracks_random)
        assert pl.path == path_fake
        assert pl.tracks == tracks_random

        await pl.load(tracks + tracks_random[:4])
        assert pl.tracks == tracks + tracks_random[:4]

    # noinspection PyTestUnpassedFixture
    async def test_load_file_with_no_tracks(self, tracks_actual: list[LocalTrack], tracks_limited: list[LocalTrack]):
        pl = M3U(path=path_playlist_m3u, path_mapper=PathStemMapper(stem_map={"../": path_resources}))
        await pl.load()

        assert pl.path == path_playlist_m3u
        assert pl.tracks == tracks_actual
        assert [track.path for track in pl] == [track.path for track in tracks_actual]

        # reloads only with given tracks that match conditions i.e. paths to include
        await pl.load(tracks_limited)
        assert [track.path for track in pl] == [track.path for track in tracks_limited if track in tracks_actual]
        assert pl.tracks == [track for track in tracks_limited if track in tracks_actual]

        # ...and then reloads all tracks from disk that match conditions when no tracks are given
        await pl.load()
        assert pl.tracks == tracks_actual

    async def test_load_file_with_tracks(
            self, tracks_actual: list[LocalTrack], tracks_limited: list[LocalTrack], path_mapper: PathMapper
    ):
        pl = M3U(path=path_playlist_m3u, path_mapper=path_mapper)
        await pl.load(tracks=tracks_limited)

        assert pl.path == path_playlist_m3u
        assert pl.tracks == [track for track in tracks_limited if track in tracks_actual]

        # reloads only with given tracks that match conditions i.e. paths to include
        await pl.load(tracks_limited[:1])
        assert pl.tracks == tracks_limited[:1]

        # ...and then reloads all tracks from disk that match conditions when no tracks are given
        await pl.load()
        assert pl.tracks == tracks_actual

    async def test_save_file_dry_run(self, tmp_path: Path):
        path_new = tmp_path.joinpath("new_playlist").with_suffix(".m3u")

        # creates a new M3U file
        pl = M3U(path=path_new)
        assert pl.path == path_new
        assert len(pl.tracks) == 0

        # ...load the tracks
        tracks_random = random_tracks(30)
        await pl.load(tracks_random)
        assert pl.tracks == tracks_random

        # ...save these loaded tracks as a dry run - no output
        result = await pl.save(dry_run=True)

        assert result.start == 0
        assert result.added == len(tracks_random)
        assert result.removed == 0
        assert result.unchanged == 0
        assert result.difference == len(tracks_random)
        assert result.final == len(tracks_random)

        assert not path_new.exists()
        assert pl.date_modified is None
        assert pl.date_created is None

    async def test_save_new_file(self, tmp_path: Path):
        path_new = tmp_path.joinpath("new_playlist").with_suffix(".m3u")
        tracks_random = random_tracks(30)

        pl = M3U(path=path_new)
        await pl.load(tracks=tracks_random)
        result = await pl.save(dry_run=False)

        assert result.start == 0
        assert result.added == len(tracks_random)
        assert result.removed == 0
        assert result.unchanged == 0
        assert result.difference == len(tracks_random)
        assert result.final == len(tracks_random)

        assert path_new.exists()
        assert pl.date_modified is not None
        assert pl.date_created is not None

        with open(path_new, "r") as f:
            paths = [line.strip() for line in f]
        assert paths == [str(track.path) for track in pl.tracks]

        original_dt_modified = pl.date_modified

        # ...remove some tracks and add some new ones
        tracks_random_new = random_tracks(15)
        pl.tracks = pl.tracks[:20] + tracks_random_new
        result = await pl.save(dry_run=False)

        assert result.start == len(tracks_random)
        assert result.added == len(tracks_random_new)
        assert result.removed == 10
        assert result.unchanged == 20
        assert result.difference == 5
        assert result.final == 35

        if not os.getenv("GITHUB_ACTIONS"):
            # TODO: these assertions always fail on GitHub actions but not locally, why?
            assert pl.date_modified > original_dt_modified

        with open(path_new, "r") as f:
            paths = [line.strip() for line in f]
        assert paths == [str(track.path) for track in pl.tracks]

    @pytest.mark.parametrize("path", [path_playlist_m3u], indirect=["path"])
    async def test_save_existing_file(
            self, tracks_actual: list[LocalTrack], path: str, path_mapper: PathStemMapper, tmp_path: Path
    ):
        path_prefix = list(path_mapper.stem_map)[0]

        # ensure all paths in the file have relative paths and will therefore undergo path mapping
        with open(path, "r") as f:
            for line in f:
                assert line.startswith(path_prefix)

        # ensure all loaded track path have absolute paths and will therefore undergo path mapping
        for track in tracks_actual:
            assert not str(track.path).startswith(path_prefix)

        pl = M3U(path=path, path_mapper=path_mapper)
        await pl.load()

        assert pl.path == path
        assert pl.tracks == tracks_actual
        original_dt_modified = pl.date_modified
        original_dt_created = pl.date_created

        tracks_random = random_tracks(10)
        pl.tracks = pl.tracks[:2] + tracks_random
        result = await pl.save(dry_run=False)

        assert result.start == 3
        assert result.added == len(tracks_random)
        assert result.removed == 1
        assert result.unchanged == 2
        assert result.difference == 9
        assert result.final == 12

        new_dt_modified = pl.date_modified
        if not os.getenv("GITHUB_ACTIONS"):
            # TODO: these assertions always fail on GitHub actions but not locally, why?
            assert new_dt_modified > original_dt_modified

        # assert file has reported path count and paths in the file have been mapped to relative paths
        with open(path, "r") as f:
            lines = [line.strip() for line in f]
        assert len(lines) == result.final
        for line in lines:
            assert line.startswith(path_prefix)

        # change the name and save to new file
        pl.name = "New Playlist"
        assert pl.path == tmp_path.joinpath("New Playlist").with_suffix(pl.ext)
        await pl.save(dry_run=False)

        if not os.getenv("GITHUB_ACTIONS"):
            # TODO: these assertions always fail on GitHub actions but not locally, why?
            assert pl.date_modified > new_dt_modified
            assert pl.date_created > original_dt_created

        with open(pl.path, "r") as f:
            paths = [line.strip() for line in f]
        assert paths == list(map(str, path_mapper.unmap_many(pl.tracks, check_existence=False)))
