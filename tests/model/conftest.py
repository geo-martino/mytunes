from random import sample, choice

import pytest
from faker import Faker

from musify.model import MusifyResource
from musify.model.collection.playlist import Playlist, MutablePlaylist
from musify.model.item.album import Album
from musify.model.item.artist import Artist
from musify.model.item.genre import Genre
from musify.model.item.track import Track
from tests.utils import GENRES, SimpleURI


@pytest.fixture
def models(
        tracks: list[Track],
        artists: list[Artist],
        albums: list[Album],
        playlists: list[Playlist]
) -> list[MusifyResource]:
    return [*tracks, *artists, *albums, *playlists]


@pytest.fixture
def tracks(faker: Faker) -> list[Track]:
    return [
        Track(name=faker.sentence(nb_words=faker.random_int(1, 5)))
        for _ in range(faker.random_int(15, 30))
    ]


@pytest.fixture
def artists(faker: Faker) -> list[Artist]:
    return [
        Artist(name=faker.sentence(nb_words=faker.random_int(1, 5)))
        for _ in range(faker.random_int(5, 10))
    ]


@pytest.fixture
def albums(faker: Faker) -> list[Album]:
    return [
        Album(name=faker.sentence(nb_words=faker.random_int(1, 5)))
        for _ in range(faker.random_int(5, 10))
    ]


@pytest.fixture
def genres(faker: Faker) -> list[Genre]:
    return [Genre(name=genre) for genre in sample(GENRES, k=faker.random_int(3, 6))]


@pytest.fixture
def playlists(faker: Faker) -> list[Playlist]:
    return [MutablePlaylist(name=faker.sentence()) for _ in range(faker.random_int(10, 30))]


@pytest.fixture
def uri(models: list[MusifyResource], faker: Faker) -> SimpleURI:
    return SimpleURI.from_id(
        faker.random_int(int(10e9), int(10e10)), kind=choice(models).type, source=faker.word()
    )


@pytest.fixture
def uris(models: list[MusifyResource], faker: Faker) -> list[SimpleURI]:
    seen = set()
    uris = []

    for model in models:
        source = None
        while source is None or source in seen:
            source = faker.word()

        uris.append(SimpleURI.from_id(faker.random_int(int(10e9), int(10e10)), kind=model.type, source=source))
        seen.add(source)

    return uris
