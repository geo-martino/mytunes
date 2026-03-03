import pytest
from faker import Faker

from musify.local.item.album import LocalAlbum
from musify.models.properties.uri import URI
from tests.models.testers import UniqueKeyTester
from tests.utils import SimpleURI


class TestLocalAlbum(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> LocalAlbum:
        uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=LocalAlbum.type, source=faker.word()
        )
        return LocalAlbum(name=faker.word(), uri=uri)
