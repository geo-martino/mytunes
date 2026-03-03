from unittest.mock import patch, Mock

import pytest
from faker import Faker

from musify.remote.collection.library import RemoteLibrary
from tests.models.testers import UniqueKeyTester
from tests.utils import SimpleURI


class TestLibrary(UniqueKeyTester):
    @pytest.fixture
    @patch.multiple(
        RemoteLibrary,
        __abstractmethods__=set(),
        load=Mock(),
        load_tracks=Mock(),
        log_tracks=Mock(),
        load_playlists=Mock(),
        log_playlists=Mock(),
    )
    def model(self, faker: Faker) -> RemoteLibrary:
        uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=RemoteLibrary.type, source=faker.word()
        )
        return RemoteLibrary(name=faker.word(), uri=uri)
