import pytest
from faker import Faker

from mytunes._models.item.track import Track
from mytunes._models.properties.order import Position


@pytest.fixture
def tracks(tracks: list[Track], faker: Faker) -> list[Track]:
    total = faker.random_int(50, 100)
    for track in tracks:
        track.artist = faker.name()
        track.track = Position(number=faker.random_int(1, total), total=total)
    return tracks


@pytest.fixture
def tracks_group(tracks: list[Track], faker: Faker) -> list[Track]:
    tracks = list(faker.random_elements(tracks, unique=True))
    name = faker.sentence()

    for track in tracks:
        track.name = name
    return tracks
