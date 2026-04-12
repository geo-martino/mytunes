import pytest
from faker import Faker

from mytunes._models.item.user import RemoteUser
from tests.remote import SimpleURI
from tests.testers import UniqueKeyTester


class TestRemoteUser(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> RemoteUser:
        uri = SimpleURI.create_random(RemoteUser.type)
        return RemoteUser[SimpleURI](name=faker.word(), email=faker.email(), uri=uri)
