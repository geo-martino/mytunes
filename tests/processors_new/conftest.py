from random import sample, choice

import pytest
from faker import Faker

from musify.local.item.track import LocalTrack
from musify.models import MusifyResource
from musify.models.collection.playlist import Playlist, MutablePlaylist
from musify.models.item.album import Album
from musify.models.item.artist import Artist
from musify.models.item.genre import Genre
from musify.models.item.track import Track
from tests.utils import GENRES, SimpleURI


@pytest.fixture
def tracks(faker: Faker) -> list[LocalTrack]:
    return [
        LocalTrack(name=faker.sentence(nb_words=faker.random_int(1, 5)), path=faker.file_path())
        for _ in range(faker.random_int(15, 30))
    ]
