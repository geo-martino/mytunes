import pytest
from faker import Faker

from musify.local._collection.album import LocalAlbumCollection
from tests.remote import SimpleURI
from tests.testers import NoUniqueKeyTester


class TestLocalAlbumCollection(NoUniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> LocalAlbumCollection:
        uri = SimpleURI.create_random(LocalAlbumCollection.type)
        return LocalAlbumCollection(name=faker.word(), uri=uri)
