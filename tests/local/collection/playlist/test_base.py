import os
from pathlib import Path

import pytest
from faker import Faker
from mytunes._models.properties.path import PathStemMapper
from mytunes.local._collection.library import LocalLibrary
from mytunes.local._collection.library.musicbee import MusicBee
from mytunes.local._collection.playlist import LocalPlaylistFile
from tests.testers import UniqueKeyTester


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
    mapper = PathStemMapper(stem_map={
        "/mnt/media/Music": os.getenv("TEST_PL_LIBRARY", ""),
        "../": os.getenv("TEST_PL_LIBRARY", ""),
        "M:/Music": os.getenv("TEST_PL_LIBRARY", ""),
        r"M:\Music": os.getenv("TEST_PL_LIBRARY", ""),
    })

    library = MusicBee(musicbee_folder=Path(os.getenv("TEST_PL_LIBRARY")).joinpath("MusicBee"), path_mapper=mapper)
    await library.load_tracks()
    return library


@pytest.mark.manual
@pytest.mark.skipif(
    "not config.getoption('-m') and not config.getoption('-k')",
    reason="Only runs when the test or marker is specified explicitly by the user",
)
@pytest.mark.parametrize("source,expected", [
    (path, Path(os.getenv("TEST_PL_COMPARISON", "")).joinpath(path.stem).with_suffix(".m3u"))
    for path in (
            list(Path(os.getenv("TEST_PL_SOURCE", "")).rglob(str(Path("**", "*.xautopf")))) +
            list(Path(os.getenv("TEST_PL_SOURCE", "")).rglob(str(Path("**", "*.m3u"))))
    )
])
async def test_playlist_paths_manual(library: LocalLibrary, source: Path, expected: Path):
    assert source.is_file()
    assert expected.is_file()

    pl = await library.load_playlist(source)

    with open(expected, "r", encoding="utf-8") as file:
        paths_expected = [library.path_mapper.map(line.strip(), check_existence=False) for line in file]

    paths_actual = list(map(str, (track.path for track in pl.tracks)))
    assert sorted(paths_actual) == sorted(paths_expected)
    assert paths_actual == paths_expected
