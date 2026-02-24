from pathlib import Path
from random import choice
from typing import get_args

import pytest
from faker import Faker

from musify.local.item.album import LocalAlbum
from musify.local.item.artist import LocalArtist
from musify.local.item.track import LocalTrack, LocalTrackType
from musify.models.collection.playlist import MutablePlaylist, Playlist


@pytest.fixture
def tracks(faker: Faker, tmp_path: Path) -> list[LocalTrack]:
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


@pytest.fixture
def artists(faker: Faker) -> list[LocalArtist]:
    return [
        LocalArtist(name=faker.sentence(nb_words=faker.random_int(1, 5)))
        for _ in range(faker.random_int(5, 10))
    ]


@pytest.fixture
def albums(faker: Faker) -> list[LocalAlbum]:
    return [
        LocalAlbum(name=faker.sentence(nb_words=faker.random_int(1, 5)))
        for _ in range(faker.random_int(5, 10))
    ]


@pytest.fixture
def playlists(tracks: list[LocalTrack], faker: Faker) -> list[Playlist]:
    return [
        MutablePlaylist(name=faker.sentence(), tracks=faker.random_elements(tracks, length=faker.random_int(5, 15)))
        for _ in range(faker.random_int(10, 30))
    ]
