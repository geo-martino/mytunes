import pytest
from faker import Faker

from musify.local.item.artist import LocalArtist
from tests.models.testers import NoUniqueKeyTester
from tests.utils import SimpleURI


class TestLocalArtist(NoUniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> LocalArtist:
        uri = SimpleURI.create_random(LocalArtist.type)
        return LocalArtist(name=faker.word(), uri=uri)
