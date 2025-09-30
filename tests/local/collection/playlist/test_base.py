from pathlib import Path

import pytest
from faker import Faker

from musify.local.collection.playlist._base import _LocalPlaylist
from tests.models.testers import UniqueKeyTester


class TestLocalPlaylist(UniqueKeyTester):

    @pytest.fixture
    async def model(self, faker: Faker, tmp_path: Path) -> _LocalPlaylist:
        return _LocalPlaylist(path=tmp_path.joinpath("does_not_exist").with_suffix(".m3u"))

    def test_extract_name_from_path(self, faker: Faker) -> None:
        path = Path(faker.file_path(absolute=False, extension="m3u"))
        pl = _LocalPlaylist(path=path)
        assert pl.name == path.stem
