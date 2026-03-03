import pytest
from faker import Faker

from musify.local.collection.album import LocalAlbumCollection
from musify.models.item.track import Track
from musify.models.properties.uri import URI
from tests.models.testers import UniqueKeyTester
from tests.utils import SimpleURI


class TestLocalAlbumCollection(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> LocalAlbumCollection:
        uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=LocalAlbumCollection.type, source=faker.word()
        )
        return LocalAlbumCollection(name=faker.word(), uri=uri)
