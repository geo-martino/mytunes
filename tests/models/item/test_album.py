import pytest
from faker import Faker

from musify.models.item.album import Album, HasAlbums, RemoteAlbum, HasAlbum
from musify.models.item.artist import Artist
from tests.models.testers import NoUniqueKeyTester, UniqueKeyTester
from tests.utils import SimpleURI


class TestAlbum(NoUniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> Album:
        uri = SimpleURI.create_random(Album.type)
        return Album(name=faker.word(), uri=uri)


class TestHasAlbum(NoUniqueKeyTester):
    @pytest.fixture
    def model(self, album: Album) -> HasAlbum:
        return HasAlbum(album=album)

    def test_set_album_artist(self, model: HasAlbum, artists: list[Artist], faker: Faker):
        assert not model.album.artists
        artists = faker.random_elements(artists, length=3, unique=True)

        model.album_artist = artists[0]
        assert model.album.artists == [artists[0]]

        model.album_artist = artists[1]
        assert model.album.artists == [artists[1], artists[0]]

        model.album_artist = artists[2]
        assert model.album.artists == [artists[2], artists[1], artists[0]]

    def test_set_album_artist_skips_on_existing(self, model: HasAlbum, artists: list[Artist], faker: Faker):
        artists = faker.random_elements(artists, length=3, unique=True)
        model.album.artists = artists

        model.album_artist = faker.random_element(artists)
        assert model.album.artists == artists

        model.album_artist = faker.random_element(artists).name
        assert model.album.artists == artists

    def test_set_compilation(self, model: HasAlbum, faker: Faker):
        compilation = faker.boolean()
        model.compilation = compilation
        assert model.album.compilation == compilation


class TestHasAlbums(NoUniqueKeyTester):
    @pytest.fixture
    def model(self, albums: list[Album]) -> HasAlbums:
        return HasAlbums(albums=albums)

    def test_from_string(self, albums: list[Album]):
        album = HasAlbums._join_tags(album.name for album in albums)
        model = HasAlbums(album=album)
        assert [album.name for album in model.albums] == [album.name for album in albums]


class TestRemoteAlbum(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> RemoteAlbum:
        uri = SimpleURI.create_random(RemoteAlbum.type)
        return RemoteAlbum(name=faker.word(), uri=uri)
