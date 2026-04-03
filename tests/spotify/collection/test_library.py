import pytest

from musify.spotify.api import SpotifyAPI
from musify.spotify.collection.library import SpotifyLibrary
from tests.models.testers import BaseModelTester


class TestSpotifyLibrary(BaseModelTester):
    @pytest.fixture
    def model(self, api: SpotifyAPI) -> SpotifyLibrary:
        return SpotifyLibrary(api=api)
