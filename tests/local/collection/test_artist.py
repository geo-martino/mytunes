import pytest
from faker import Faker

from musify.local._collection.artist import LocalArtistCollection
from tests.remote import SimpleURI
from tests.testers import NoUniqueKeyTester


class TestLocalArtistCollection(NoUniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> LocalArtistCollection:
        uri = SimpleURI.create_random(LocalArtistCollection.type)
        return LocalArtistCollection(name=faker.word(), uri=uri)
