import pytest
from faker import Faker

from musify.local._item.album import LocalAlbum
from tests.remote import SimpleURI
from tests.testers import NoUniqueKeyTester


class TestLocalAlbum(NoUniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> LocalAlbum:
        uri = SimpleURI.create_random(LocalAlbum.type)
        return LocalAlbum(name=faker.word(), uri=uri)
