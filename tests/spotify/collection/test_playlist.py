import pytest
from faker import Faker

from musify.spotify.collection.playlist import SpotifyPlaylist
from tests.spotify.generator import SpotifyPayloadGenerator
from tests.spotify.testers import SpotifyResourceTester


class TestSpotifyPlaylist(SpotifyResourceTester):
    @pytest.fixture
    def model(self, generator: SpotifyPayloadGenerator, faker: Faker) -> SpotifyPlaylist:
        return SpotifyPlaylist(
            name=faker.name(),
            followers=faker.random_int(),
            uri=generator.generate_uri("playlist"),
        )

    def test_response(self, generator: SpotifyPayloadGenerator):
        payload = generator.generate_playlist()
        generator.add_playlist_items(payload)

        model = SpotifyPlaylist.model_validate(payload)

        self.assert_expected_name(model, payload)
        self.assert_expected_identifiers(model, payload)
        self.assert_expected_images(model, payload)
        self.assert_expected_followers(model, payload)
