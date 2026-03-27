import pytest
from faker import Faker

from musify.models.collection.playlist import RemoteMutablePlaylist, RemotePlaylist, Playlist
from musify.models.item.album import RemoteAlbum, Album
from musify.models.item.artist import Artist, RemoteArtist
from musify.models.item.track import Track, RemoteTrack
from musify.models.user import RemoteUser
from tests.models.api.utils import MockUrlCursor
from tests.utils import SimpleURI


@pytest.fixture
def playlists(
        playlists: list[Playlist], tracks: list[Track], faker: Faker
) -> list[RemotePlaylist]:
    return [
        RemoteMutablePlaylist(
            **pl.model_dump(exclude={"tracks", "uri"}),
            owner=RemoteUser(name=faker.name(), uri=SimpleURI.create_random(RemoteUser.type)),
            cursor=MockUrlCursor(url=faker.url()),
            tracks=faker.random_elements(tracks),
            uri=SimpleURI.create_random(RemotePlaylist.type))
        for pl in playlists
    ]


@pytest.fixture
def tracks(tracks: list[Track], faker: Faker) -> list[RemoteTrack]:
    return [
        RemoteTrack(
            **track.model_dump(exclude={"uri"}),
            uri=SimpleURI.create_random(RemoteTrack.type))
        for track in tracks
    ]


@pytest.fixture
def artists(artists: list[Artist], faker: Faker) -> list[RemoteArtist]:
    return [
        RemoteArtist(
            **artist.model_dump(exclude={"uri"}),
            uri=SimpleURI.create_random(RemoteArtist.type))
        for artist in artists
    ]


@pytest.fixture
def albums(albums: list[Album], faker: Faker) -> list[RemoteAlbum]:
    return [
        RemoteAlbum(
            **album.model_dump(exclude={"uri"}),
            uri=SimpleURI.create_random(RemoteAlbum.type))
        for album in albums
    ]
