import pytest
from faker import Faker

from musify.local.item.track import LocalTrack


@pytest.fixture
def tracks(faker: Faker) -> list[LocalTrack]:
    return [
        LocalTrack(name=faker.sentence(nb_words=faker.random_int(1, 5)), path=faker.file_path())
        for _ in range(50)
    ]
