import pytest
from faker import Faker

from mytunes.core._item.user import RemoteUser
from tests.remote import SimpleURI


@pytest.fixture(scope="session")
def user(faker: Faker) -> RemoteUser:
    owner_uri = SimpleURI.create_random(RemoteUser.type)
    return RemoteUser(name=faker.name(), uri=owner_uri)
