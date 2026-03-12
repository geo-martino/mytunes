from abc import ABCMeta

import pytest
from yarl import URL

from musify.models.collection import PageCursor
from tests.models.testers import UniqueKeyTester


class RemoteCollectionTester(UniqueKeyTester, metaclass=ABCMeta):
    @pytest.fixture
    def cursor(self) -> PageCursor:
        return PageCursor(
            url=URL.build(scheme="http", host="example.com", path="/api/items"),
            limit=20,
            offset=0,
        )
