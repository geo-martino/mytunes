import pytest
from faker import Faker

from mytunes.core._item.track import Track
from mytunes.core.properties.order import Position


@pytest.fixture
def tracks(tracks: list[Track], faker: Faker) -> list[Track]:
    total = faker.random_int(50, 100)
    for track in tracks:
        track.artist = faker.name()
        track.track = Position(number=faker.random_int(1, total), total=total)
    return tracks
