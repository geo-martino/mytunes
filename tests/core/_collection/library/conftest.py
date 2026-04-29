import pytest
from faker import Faker
from yarl import URL

from mytunes.core._collection.playlist import RemoteMutablePlaylist, RemotePlaylist, Playlist
from mytunes.core._item.album import RemoteAlbum, Album
from mytunes.core._item.artist import Artist, RemoteArtist
from mytunes.core._item.track import Track, RemoteTrack
from mytunes.core._item.user import RemoteUser
from tests.remote import SimpleURI, MockUrlCursor


@pytest.fixture
def playlists(
        playlists: list[Playlist], tracks: list[RemoteTrack], faker: Faker
) -> list[RemoteMutablePlaylist]:
    return [
        RemoteMutablePlaylist(
            **pl.model_dump(exclude={"tracks"}),
            owner=RemoteUser(name=faker.name(), uri=SimpleURI.create_random(RemoteUser.type)),
            cursor=MockUrlCursor(url=URL(faker.url())),
            tracks=faker.random_elements(tracks),
            uri=SimpleURI.create_random(RemotePlaylist.type))
        for pl in playlists
    ]


@pytest.fixture
def tracks(tracks: list[Track], faker: Faker) -> list[RemoteTrack]:
    return [
        RemoteTrack(
            **track.model_dump(),
            uri=SimpleURI.create_random(RemoteTrack.type))
        for track in tracks
    ]


@pytest.fixture
def artists(artists: list[Artist], faker: Faker) -> list[RemoteArtist]:
    return [
        RemoteArtist(
            **artist.model_dump(),
            uri=SimpleURI.create_random(RemoteArtist.type))
        for artist in artists
    ]


@pytest.fixture
def albums(albums: list[Album], faker: Faker) -> list[RemoteAlbum]:
    return [
        RemoteAlbum(
            **album.model_dump(),
            uri=SimpleURI.create_random(RemoteAlbum.type))
        for album in albums
    ]
