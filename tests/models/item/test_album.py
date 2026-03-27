import pytest
from faker import Faker

from musify.models.item.album import Album, HasAlbums, RemoteAlbum
from tests.models.testers import NoUniqueKeyTester, UniqueKeyTester
from tests.utils import SimpleURI


class TestAlbum(NoUniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> Album:
        uri = SimpleURI.create_random(Album.type)
        return Album(name=faker.word(), uri=uri)


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
