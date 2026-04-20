from pathlib import Path
from random import choice

import pytest
from faker import Faker

from mytunes.core.api import RemoteAPI
from mytunes.local._item.track import LocalTrack
from tests.remote import MockRemoteAPI


@pytest.fixture
def local_tracks(faker: Faker, tmp_path: Path) -> list[LocalTrack]:
    """
    Yields a list of random LocalTrack objects with dynamically configured properties for testing.
    Needed by some processors that require certain fields to function properly e.g. path, added_at etc.
    """
    classes: tuple[type[LocalTrack], ...] = tuple(LocalTrack.registered_submodels)
    tracks = []
    for _ in range(50):
        cls = choice(classes)
        extension = choice(tuple(cls.supported_extensions))
        track = cls.model_validate(dict(
            name=faker.sentence(nb_words=faker.random_int(1, 5)),
            path=tmp_path.joinpath(faker.file_path(absolute=False, extension=extension)),
        ))
        tracks.append(track)

    return tracks


@pytest.fixture(scope="session")
def api() -> RemoteAPI:
    return MockRemoteAPI()
