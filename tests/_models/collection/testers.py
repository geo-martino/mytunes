from abc import ABCMeta

import pytest
from faker import Faker
from yarl import URL

from musify._models.cursors import PageCursor
from tests.remote import MockUrlCursor
from tests.testers import UniqueKeyTester


class RemoteCollectionTester(UniqueKeyTester, metaclass=ABCMeta):
    @pytest.fixture
    def cursor(self, faker: Faker) -> PageCursor:
        return MockUrlCursor(
            url=URL.build(scheme="http", host="example.com", path="/api/items"),
        )
