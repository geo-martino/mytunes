import pytest
from faker import Faker

from musify.local._collection.album import LocalAlbumCollection
from tests.models.testers import NoUniqueKeyTester
from tests.utils import SimpleURI


class TestLocalAlbumCollection(NoUniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> LocalAlbumCollection:
        uri = SimpleURI.create_random(LocalAlbumCollection.type)
        return LocalAlbumCollection(name=faker.word(), uri=uri)
