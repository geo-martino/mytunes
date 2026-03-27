import pytest
from faker import Faker

from musify.models.user import RemoteUser
from tests.models.testers import UniqueKeyTester
from tests.utils import SimpleURI


class TestRemoteUser(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> RemoteUser:
        uri = SimpleURI.create_random(RemoteUser.type)
        return RemoteUser[SimpleURI](name=faker.word(), email=faker.email(), uri=uri)
