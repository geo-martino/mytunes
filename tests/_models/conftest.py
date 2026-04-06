from random import choice

import pytest
from faker import Faker

from musify._models import ResourceModel
from musify._models.collection.playlist import Playlist
from musify._models.item.album import Album
from musify._models.item.artist import Artist
from musify._models.item.track import Track
from musify._models.item.user import RemoteUser
from tests.remote import SimpleURI


@pytest.fixture
def model(models: list[ResourceModel]) -> ResourceModel:
    return choice(models)


@pytest.fixture
def models(
        tracks: list[Track],
        artists: list[Artist],
        albums: list[Album],
        playlists: list[Playlist]
) -> list[ResourceModel]:
    return [*tracks, *artists, *albums, *playlists]


@pytest.fixture(scope="session")
def user(faker: Faker) -> RemoteUser:
    owner_uri = SimpleURI.create_random(RemoteUser.type)
    return RemoteUser(name=faker.name(), uri=owner_uri)
