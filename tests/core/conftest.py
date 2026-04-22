from random import choice

import pytest
from faker import Faker

from mytunes._base.resource import ResourceModel
from mytunes.core._collection.playlist import Playlist
from mytunes.core._item.album import Album
from mytunes.core._item.artist import Artist
from mytunes.core._item.track import Track
from mytunes.core._item.user import RemoteUser
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
