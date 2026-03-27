import pytest
from faker import Faker

from musify.local.item.album import LocalAlbum
from tests.models.testers import NoUniqueKeyTester
from tests.utils import SimpleURI


class TestLocalAlbum(NoUniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> LocalAlbum:
        uri = SimpleURI.create_random(LocalAlbum.type)
        return LocalAlbum(name=faker.word(), uri=uri)
