from random import choice

import pytest
from faker import Faker

from musify.models import BaseResource
from musify.models.collection.playlist import Playlist, RemotePlaylist
from musify.models.item.album import Album, RemoteAlbum
from musify.models.item.artist import Artist, RemoteArtist
from musify.models.item.track import Track, RemoteTrack
from musify.models.user import RemoteUser
from tests.models.api.utils import MockUrlCursor
from tests.utils import SimpleURI


@pytest.fixture
def model(models: list[BaseResource]) -> BaseResource:
    return choice(models)


@pytest.fixture
def models(
        tracks: list[Track],
        artists: list[Artist],
        albums: list[Album],
        playlists: list[Playlist]
) -> list[BaseResource]:
    return [*tracks, *artists, *albums, *playlists]


@pytest.fixture
def user(faker: Faker) -> RemoteUser:
    owner_uri = SimpleURI.from_id(faker.pystr(22, 22), kind=RemoteUser.type)
    return RemoteUser(name=faker.name(), uri=owner_uri)


@pytest.fixture
def playlists(playlists: list[Playlist], user: RemoteUser, faker: Faker) -> list[RemotePlaylist]:
    return [
        RemotePlaylist(
            **pl.model_dump(),
            owner=RemoteUser(name=faker.name(), uri=SimpleURI.from_id(faker.pystr(22, 22), kind=RemoteUser.type)),
            cursor=MockUrlCursor(url=faker.url())
        )
        for pl in playlists
    ]


@pytest.fixture
def tracks(tracks: list[Track]) -> list[RemoteTrack]:
    return [RemoteTrack(**track.model_dump()) for track in tracks]


@pytest.fixture
def artists(artists: list[Artist]) -> list[RemoteArtist]:
    return [RemoteArtist(**artist.model_dump()) for artist in artists]


@pytest.fixture
def albums(albums: list[Album]) -> list[RemoteAlbum]:
    return [RemoteAlbum(**album.model_dump()) for album in albums]
