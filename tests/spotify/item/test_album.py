from datetime import date

import pytest
from faker import Faker
from pydantic import Json
from yarl import URL

from musify.spotify.item.album import SpotifyAlbum
from musify.spotify.properties.uri import SpotifyResourceURI
from tests.spotify.generator import SpotifyPayloadGenerator
from tests.spotify.testers import SpotifyResourceTester
from tests.utils import GENRES


class TestSpotifyAlbum(SpotifyResourceTester):
    @pytest.fixture
    def model(self, generator: SpotifyPayloadGenerator, faker: Faker) -> SpotifyAlbum:
        return SpotifyAlbum(
            name=faker.name(),
            uri=generator.generate_uri("album"),
        )

    def test_response(self, generator: SpotifyPayloadGenerator):
        payload = generator.generate_album()
        generator.add_album_extended_properties(payload)

        model = SpotifyAlbum.model_validate(payload)

        self.assert_expected_name(model, payload)
        self.assert_expected_identifiers(model, payload)
        self.assert_expected_images(model, payload)
        self.assert_expected_genres(model, payload)
        self.assert_expected_popularity(model, payload)
