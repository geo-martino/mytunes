from unittest.mock import patch, Mock

import pytest
from faker import Faker

from musify.remote.collection.library import RemoteLibrary, RemoteMutableLibrary
from tests.models.testers import MusifyModelTester


class TestRemoteLibrary(MusifyModelTester):
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
        return RemoteLibrary(name=faker.word())


class TestRemoteMutableLibrary(MusifyModelTester):
    @pytest.fixture
    @patch.multiple(
        RemoteMutableLibrary,
        __abstractmethods__=set(),
        load=Mock(),
        load_tracks=Mock(),
        log_tracks=Mock(),
        load_playlists=Mock(),
        log_playlists=Mock(),
    )
    def model(self, faker: Faker) -> RemoteMutableLibrary:
        return RemoteMutableLibrary(name=faker.word())
