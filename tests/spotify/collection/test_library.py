import pytest
from faker import Faker

from musify.spotify.api import SpotifyAPI
from musify.spotify.collection.library import SpotifyLibrary
from tests.models.testers import MusifyModelTester


class TestSpotifyLibrary(MusifyModelTester):
    @pytest.fixture
    def api(self, faker: Faker) -> SpotifyAPI:
        return SpotifyAPI(client_id=faker.uuid4(), client_secret=faker.uuid4())

    @pytest.fixture
    def model(self, api: SpotifyAPI) -> SpotifyLibrary:
        return SpotifyLibrary(api=api)
