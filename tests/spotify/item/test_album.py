import pytest
from faker import Faker

from musify.models.properties.date import SparseDate
from musify.spotify.item.album import SpotifyAlbum
from tests.spotify.generator import SpotifyPayloadGenerator
from tests.spotify.testers import SpotifyResourceTester


class TestSpotifyAlbum(SpotifyResourceTester):
    @pytest.fixture
    def model(self, generator: SpotifyPayloadGenerator, faker: Faker) -> SpotifyAlbum:
        return SpotifyAlbum(
            name=faker.name(),
            uri=generator.generate_uri("album"),
            released_at=SparseDate.model_validate(faker.date()),
            compilation=faker.boolean(),
        )

    def test_response(self, generator: SpotifyPayloadGenerator):
        payload = generator.generate_album()
        generator.add_album_artists(payload)
        generator.add_album_extended_properties(payload)

        model = SpotifyAlbum.model_validate(payload)

        self.assert_expected_name(model, payload)
        self.assert_expected_identifiers(model, payload)
        self.assert_expected_images(model, payload)
        self.assert_expected_artists(model, payload)
        self.assert_expected_genres(model, payload)
        self.assert_expected_rating(model, payload)

        assert model.compilation is (payload["album_type"] == "compilation")
