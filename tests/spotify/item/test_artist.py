import pytest
from faker import Faker
from pydantic import Json

from musify.spotify.item.artist import SpotifyArtist
from musify.spotify.properties.uri import SpotifyResourceURI
from tests.spotify.generator import SpotifyPayloadGenerator
from tests.spotify.testers import SpotifyResourceTester
from tests.utils import GENRES


class TestSpotifyArtist(SpotifyResourceTester):
    @pytest.fixture
    def model(self, generator: SpotifyPayloadGenerator, faker: Faker) -> SpotifyArtist:
        return SpotifyArtist(
            name=faker.name(),
            followers=faker.random_int(),
            popularity=faker.random_int(0, 100),
            uri=generator.generate_uri("artist"),
        )

    def test_response(self, generator: SpotifyPayloadGenerator):
        payload = generator.generate_artist(properties=True)
        generator.add_artist_extended_properties(payload)

        model = SpotifyArtist.model_validate(payload)

        self.assert_expected_name(model, payload)
        self.assert_expected_identifiers(model, payload)
        self.assert_expected_images(model, payload)
        self.assert_expected_genres(model, payload)
        self.assert_expected_followers(model, payload)
        self.assert_expected_popularity(model, payload)
