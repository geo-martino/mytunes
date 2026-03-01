from pathlib import Path
from random import sample, choice
from typing import get_args

import pytest
from faker import Faker

from musify.local.item.album import LocalAlbum
from musify.local.item.artist import LocalArtist
from musify.local.item.genre import LocalGenre
from musify.local.item.track import LocalTrack
from musify.models import MusifyResource
from tests.utils import GENRES, SimpleURI


@pytest.fixture
def models(
        tracks: list[LocalTrack],
        artists: list[LocalArtist],
        albums: list[LocalAlbum],
) -> list[MusifyResource]:
    return [*tracks, *artists, *albums]


@pytest.fixture
def track(faker: Faker, tmp_path: Path) -> LocalTrack:
    classes: tuple[type[LocalTrack], ...] = tuple(LocalTrack.registered_submodels)
    cls = choice(classes)
    extension = choice(tuple(cls.supported_extensions))
    track = cls.model_validate(dict(
        name=faker.sentence(nb_words=faker.random_int(1, 5)),
        path=tmp_path.joinpath(faker.file_path(absolute=False, extension=extension)),
    ))

    return track


@pytest.fixture
def tracks(faker: Faker, tmp_path: Path) -> list[LocalTrack]:
    classes: tuple[type[LocalTrack], ...] = tuple(LocalTrack.registered_submodels)
    tracks = []
    for _ in range(faker.random_int(30, 50)):
        cls = choice(classes)
        extension = choice(tuple(cls.supported_extensions))
        track = cls.model_validate(dict(
            name=faker.sentence(nb_words=faker.random_int(1, 5)),
            path=tmp_path.joinpath(faker.file_path(absolute=False, extension=extension)),
        ))
        tracks.append(track)

    return tracks


@pytest.fixture
def artist(faker: Faker) -> LocalArtist:
    return LocalArtist(name=faker.sentence(nb_words=faker.random_int(1, 5)))


@pytest.fixture
def artists(faker: Faker) -> list[LocalArtist]:
    return [
        LocalArtist(name=faker.sentence(nb_words=faker.random_int(1, 5)))
        for _ in range(faker.random_int(5, 10))
    ]


@pytest.fixture
def album(faker: Faker) -> LocalAlbum:
    return LocalAlbum(name=faker.sentence(nb_words=faker.random_int(1, 5)))


@pytest.fixture
def albums(faker: Faker) -> list[LocalAlbum]:
    return [
        LocalAlbum(name=faker.sentence(nb_words=faker.random_int(1, 5)))
        for _ in range(faker.random_int(5, 10))
    ]


@pytest.fixture
def genre() -> list[LocalGenre]:
    return LocalGenre(name=choice(GENRES))


@pytest.fixture
def genres(faker: Faker) -> list[LocalGenre]:
    return [LocalGenre(name=genre) for genre in sample(GENRES, k=faker.random_int(5, 10))]


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
