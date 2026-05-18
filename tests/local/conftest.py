from pathlib import Path
from random import choice

import pytest
from faker import Faker

from mytunes._base.resource import ResourceModel
from mytunes.core._item.genre import Genre
from mytunes.local._item.album import LocalAlbum
from mytunes.local._item.artist import LocalArtist
from mytunes.local._item.genre import LocalGenre
from mytunes.local._item.track import LocalTrack


@pytest.fixture
def models(
        tracks: list[LocalTrack],
        artists: list[LocalArtist],
        albums: list[LocalAlbum],
) -> list[ResourceModel]:
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
        file_path = faker.file_path(absolute=False, extension=extension, depth=faker.random_int(1, 5))
        track = cls.model_validate(dict(
            name=faker.sentence(nb_words=faker.random_int(5, 10)),
            path=tmp_path.joinpath(file_path),
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
def genre(genre: Genre) -> LocalGenre:
    return LocalGenre(name=genre.name)


@pytest.fixture
def genres(genres: list[Genre], faker: Faker) -> list[LocalGenre]:
    return [LocalGenre(name=genre.name) for genre in genres]
