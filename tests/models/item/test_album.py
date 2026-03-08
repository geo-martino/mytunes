import pytest
from faker import Faker

from musify.models.item.album import Album, HasAlbums
from tests.models.testers import MusifyResourceTester, UniqueKeyTester
from tests.utils import SimpleURI


class TestAlbum(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> Album:
        uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=Album.type
        )
        return Album(name=faker.word(), uri=uri)


class TestHasAlbums(MusifyResourceTester):
    @pytest.fixture
    def model(self, albums: list[Album]) -> HasAlbums:
        return HasAlbums(albums=albums)

    def test_from_string(self, albums: list[Album]):
        album = HasAlbums._join_tags(album.name for album in albums)
        model = HasAlbums(album=album)
        assert [album.name for album in model.albums] == [album.name for album in albums]
