from datetime import date

import pytest
from faker import Faker
from pydantic import Json

from musify.spotify.item.track import SpotifyTrack
from musify.spotify.properties.uri import SpotifyResourceURI
from tests.spotify.generator import SpotifyPayloadGenerator
from tests.spotify.testers import SpotifyResourceTester


class TestSpotifyTrack(SpotifyResourceTester):
    @pytest.fixture
    def model(self, generator: SpotifyPayloadGenerator, faker: Faker) -> SpotifyTrack:
        return SpotifyTrack(
            name=faker.name(),
            followers=faker.random_int(),
            popularity=faker.random_int(0, 100),
            uri=generator.generate_uri("track"),
        )

    def test_response(self, generator: SpotifyPayloadGenerator):
        payload = generator.generate_track()
        generator.add_track_extended_properties(payload)

        model = SpotifyTrack.model_validate(payload)

        self.assert_expected_name(model, payload)
        self.assert_expected_identifiers(model, payload)
        self.assert_expected_images(model, payload)
        self.assert_expected_length(model, payload)
        self.assert_expected_popularity(model, payload)

        assert model.disc.number == payload["disc_number"]
        assert model.track.number == payload["track_number"]
