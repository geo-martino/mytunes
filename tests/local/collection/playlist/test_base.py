import os
from pathlib import Path

import pytest
from faker import Faker

from musify.local.collection.library import LocalLibrary
from musify.local.collection.library.musicbee import MusicBee
from musify.local.collection.playlist import LocalPlaylistFile
from musify.models.properties.file import PathStemMapper
from tests.models.testers import UniqueKeyTester


class TestLocalPlaylist(UniqueKeyTester):

    @pytest.fixture
    async def model(self, faker: Faker, tmp_path: Path) -> LocalPlaylistFile:
        return LocalPlaylistFile(path=tmp_path.joinpath("does_not_exist").with_suffix(".m3u"))

    def test_extract_name_from_path(self, faker: Faker):
        path = Path(faker.file_path(absolute=False, extension="m3u"))
        pl = LocalPlaylistFile(path=path)
        assert pl.name == path.stem


@pytest.fixture(scope="module")
async def library() -> LocalLibrary:
    """Yields a loaded :py:class:`LocalLibrary` to supply tracks for manual checking of custom playlist files"""
    mapper = PathStemMapper({"../..": os.getenv("TEST_PL_LIBRARY", "")})
    library = MusicBee(musicbee_folder=Path(os.getenv("TEST_PL_LIBRARY")).joinpath("MusicBee"), path_mapper=mapper)
    await library.load_tracks()
    return library


# noinspection PyTestUnpassedFixture, SpellCheckingInspection
@pytest.mark.manual
@pytest.mark.skipif(
    "not config.getoption('-m') and not config.getoption('-k')",
    reason="Only runs when the test or marker is specified explicitly by the user",
)
@pytest.mark.parametrize("source,expected", [
    (path, Path(os.getenv("TEST_PL_COMPARISON", "")).joinpath(path.stem).with_suffix(".m3u"))
    for path in Path(os.getenv("TEST_PL_SOURCE", "")).rglob(str(Path("**", "*.xautopf")))
])
async def test_playlist_paths_manual(library: LocalLibrary, source: Path, expected: Path):
    assert source.is_file()
    assert expected.is_file()

    pl = await library.load_playlist(source)

    with open(expected, "r", encoding="utf-8") as f:
        paths_expected = [library.path_mapper.map(line.strip()) for line in f]

    assert sorted(track.path for track in pl) == sorted(paths_expected)
    assert [track.path for track in pl] == paths_expected
