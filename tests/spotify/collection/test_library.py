import pytest

from mytunes.spotify._api import SpotifyAPI
from mytunes.spotify._collection.library import SpotifyLibrary
from tests.testers import BaseModelTester


class TestSpotifyLibrary(BaseModelTester):
    @pytest.fixture
    def model(self, api: SpotifyAPI) -> SpotifyLibrary:
        return SpotifyLibrary(api=api)
