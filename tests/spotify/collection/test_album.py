import pytest
from faker import Faker

from musify.spotify.collection.album import SpotifyAlbumCollection
from tests.spotify.generator import SpotifyPayloadGenerator
from tests.spotify.testers import SpotifyResourceTester


class TestSpotifyAlbumCollection(SpotifyResourceTester):
    @pytest.fixture
    def model(self, generator: SpotifyPayloadGenerator, faker: Faker) -> SpotifyAlbumCollection:
        return SpotifyAlbumCollection(
            name=faker.name(),
            popularity=faker.random_int(0, 100),
            uri=generator.generate_uri("album"),
            total=faker.random_int(0, 20),
        )

    def test_response(self, generator: SpotifyPayloadGenerator):
        payload = generator.generate_album()
        generator.add_album_artists(payload)
        generator.add_album_extended_properties(payload)
        generator.add_album_tracks(payload)

        model = SpotifyAlbumCollection.model_validate(payload)

        self.assert_expected_name(model, payload)
        self.assert_expected_identifiers(model, payload)
        self.assert_expected_images(model, payload)
        self.assert_expected_genres(model, payload)
        self.assert_expected_popularity(model, payload)

        self.assert_has_all_items(model, payload["tracks"]["items"], payload["tracks"]["total"])
