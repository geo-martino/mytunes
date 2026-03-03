from random import choice

import pytest

from musify.models import MusifyResource
from musify.models.collection.playlist import Playlist
from musify.models.item.album import Album
from musify.models.item.artist import Artist
from musify.models.item.track import Track


@pytest.fixture
def model(models: list[MusifyResource]) -> MusifyResource:
    return choice(models)


@pytest.fixture
def models(
        tracks: list[Track],
        artists: list[Artist],
        albums: list[Album],
        playlists: list[Playlist]
) -> list[MusifyResource]:
    return [*tracks, *artists, *albums, *playlists]
