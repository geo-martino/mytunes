from pathlib import Path
from random import choice
from typing import get_args

import pytest
from faker import Faker

from musify.local.item.track import LocalTrack, LocalTrackType


@pytest.fixture
def local_tracks(faker: Faker, tmp_path: Path) -> list[LocalTrack]:
    """
    Yields a list of random LocalTrack objects with dynamically configured properties for testing.
    Needed by some processors that require certain fields to function properly e.g. path, added_at etc.
    """
    classes = get_args(get_args(LocalTrackType.__value__)[0])
    tracks = []
    for _ in range(50):
        cls = choice(classes)
        extension = choice(tuple(get_args(cls)[0].__supported_extensions__))
        track = cls.model_validate(dict(
            name=faker.sentence(nb_words=faker.random_int(1, 5)),
            path=tmp_path.joinpath(faker.file_path(absolute=False, extension=extension)),
        ))
        tracks.append(track)

    return tracks
