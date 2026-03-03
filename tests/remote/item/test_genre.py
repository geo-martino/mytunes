from random import choice

import pytest

from musify.models.properties.uri import URI
from musify.remote.item.genre import RemoteGenre
from tests.models.testers import UniqueKeyTester
from tests.utils import GENRES


class TestRemoteGenre(UniqueKeyTester):
    @pytest.fixture
    def model(self, uri: URI) -> RemoteGenre:
        return RemoteGenre(name=choice(GENRES), uri=uri)
