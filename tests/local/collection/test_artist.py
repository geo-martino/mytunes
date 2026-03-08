import pytest
from faker import Faker

from musify.local.collection.artist import LocalArtistCollection
from tests.models.testers import UniqueKeyTester
from tests.utils import SimpleURI


class TestLocalArtistCollection(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> LocalArtistCollection:
        uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=LocalArtistCollection.type
        )
        return LocalArtistCollection(name=faker.word(), uri=uri)
