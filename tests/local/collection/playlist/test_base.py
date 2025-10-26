from pathlib import Path

import pytest
from faker import Faker

from musify.local.collection.playlist._base import LocalPlaylistFile
from tests.models.testers import UniqueKeyTester


class TestLocalPlaylist(UniqueKeyTester):

    @pytest.fixture
    async def model(self, faker: Faker, tmp_path: Path) -> LocalPlaylistFile:
        return LocalPlaylistFile(path=tmp_path.joinpath("does_not_exist").with_suffix(".m3u"))

    def test_extract_name_from_path(self, faker: Faker):
        path = Path(faker.file_path(absolute=False, extension="m3u"))
        pl = LocalPlaylistFile(path=path)
        assert pl.name == path.stem
