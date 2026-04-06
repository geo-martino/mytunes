import pytest
from faker import Faker

from musify.spotify._item.artist import SpotifyArtist
from tests.spotify.generator import SpotifyPayloadGenerator
from tests.spotify.testers import SpotifyResourceTester


class TestSpotifyArtist(SpotifyResourceTester):
    @pytest.fixture
    def model(self, generator: SpotifyPayloadGenerator, faker: Faker) -> SpotifyArtist:
        return SpotifyArtist(
            name=faker.name(),
            uri=generator.generate_uri("artist"),
        )

    def test_response(self, generator: SpotifyPayloadGenerator):
        payload = generator.generate_artist()
        generator.add_artist_extended_properties(payload)

        model = SpotifyArtist.model_validate(payload)

        self.assert_expected_name(model, payload)
        self.assert_expected_identifiers(model, payload)
        self.assert_expected_images(model, payload)
        self.assert_expected_genres(model, payload)
        self.assert_expected_followers(model, payload)
        self.assert_expected_rating(model, payload)
