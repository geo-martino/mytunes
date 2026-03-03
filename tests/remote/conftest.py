from random import choice

import pytest
from faker import Faker

from musify.models.collection.playlist import Playlist
from musify.models.item.album import Album
from musify.models.item.artist import Artist
from musify.models.item.track import Track
from tests.utils import SimpleURI


@pytest.fixture
def uri(faker: Faker) -> SimpleURI:
    types = [
        Track.type,
        Album.type,
        Artist.type,
        Playlist.type,
    ]
    return SimpleURI.from_id(
        faker.random_int(int(10e9), int(10e10)), kind=choice(types), source=faker.word()
    )
