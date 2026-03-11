import pytest
from faker import Faker

from musify.spotify.properties.music import HasSpotifyKeySignature
from tests.models.testers import BaseResourceTester


class TestHasSpotifyKeySignature(BaseResourceTester):
    @pytest.fixture
    def model(self, faker: Faker) -> HasSpotifyKeySignature:
        return HasSpotifyKeySignature(
            root=faker.random_int(min=0, max=11), mode=faker.random_int(0, 1)
        )

    def test_from_spotify_response(self):
        data = {
            "key": -1,
            "mode": 0,
        }
        model = HasSpotifyKeySignature.model_validate(data)
        assert model.key is None

        data = {
            "key": 0,
            "mode": 1,
        }
        model = HasSpotifyKeySignature.model_validate(data)
        assert model.key.root == 0
        assert model.key.mode == 1
