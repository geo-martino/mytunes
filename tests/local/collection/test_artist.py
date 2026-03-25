import pytest
from faker import Faker

from musify.local.collection.artist import LocalArtistCollection
from tests.models.testers import NoUniqueKeyTester
from tests.utils import SimpleURI


class TestLocalArtistCollection(NoUniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> LocalArtistCollection:
        uri = SimpleURI.from_id(
            faker.pystr(22, 22), kind=LocalArtistCollection.type
        )
        return LocalArtistCollection(name=faker.word(), uri=uri)
