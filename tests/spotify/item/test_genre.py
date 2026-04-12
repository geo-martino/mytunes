import pytest
from faker import Faker

from mytunes._models.item.genre import Genre
from mytunes.spotify._item.genre import SpotifyGenre
from tests.spotify.testers import SpotifyResourceTester


class TestSpotifyGenre(SpotifyResourceTester):
    @pytest.fixture
    def model(self, genre: Genre) -> SpotifyGenre:
        return SpotifyGenre(
            name=genre.name,
        )

    def test_response(self, model: SpotifyGenre, faker: Faker):
        payload = model.name
        model = SpotifyGenre.model_validate(payload)

        assert model.name == payload
