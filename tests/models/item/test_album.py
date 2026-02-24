import pytest
from faker import Faker

from musify.models.item.album import Album, HasAlbums
from musify.models.properties.uri import URI
from tests.models.testers import MusifyResourceTester, UniqueKeyTester


class TestAlbum(UniqueKeyTester):
    @pytest.fixture
    def model(self, uri: URI, faker: Faker) -> Album:
        return Album(name=faker.word(), uri=uri)


class TestHasAlbums(MusifyResourceTester):
    @pytest.fixture
    def model(self, albums: list[Album]) -> HasAlbums:
        return HasAlbums(albums=albums)

    def test_from_string(self, albums: list[Album]):
        album = HasAlbums._join_tags(album.name for album in albums)
        model = HasAlbums(album=album)
        assert [album.name for album in model.albums] == [album.name for album in albums]
