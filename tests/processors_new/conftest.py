from pathlib import Path

import pytest
from faker import Faker

from musify.local.item.track import LocalTrack


@pytest.fixture
def tracks(faker: Faker, tmp_path: Path) -> list[LocalTrack]:
    return [
        LocalTrack(
            name=faker.sentence(nb_words=faker.random_int(1, 5)),
            path=tmp_path.joinpath(faker.file_path(absolute=False))
        )
        for _ in range(50)
    ]
