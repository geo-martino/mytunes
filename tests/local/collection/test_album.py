import pytest
from faker import Faker

from musify.local.collection.album import LocalAlbumCollection
from tests.models.testers import NoUniqueKeyTester
from tests.utils import SimpleURI


class TestLocalAlbumCollection(NoUniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> LocalAlbumCollection:
        uri = SimpleURI.from_id(
            faker.pystr(22, 22), kind=LocalAlbumCollection.type
        )
        return LocalAlbumCollection(name=faker.word(), uri=uri)
