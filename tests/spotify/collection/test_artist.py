import pytest
from faker import Faker
from yarl import URL

from musify.spotify.collection._base import SpotifyItemsCursor
from musify.spotify.collection.artist import SpotifyArtistCollection
from tests.spotify.generator import SpotifyPayloadGenerator
from tests.spotify.testers import SpotifyResourceTester


class TestSpotifyArtistCollection(SpotifyResourceTester):
    @pytest.fixture
    def model(self, generator: SpotifyPayloadGenerator, faker: Faker) -> SpotifyArtistCollection:
        kind = "artist"
        artist_id = generator.generate_resource_id()

        return SpotifyArtistCollection(
            name=faker.name(),
            uri=generator.generate_uri("artist", artist_id),
            total=faker.random_int(1, 50),
            cursor=SpotifyItemsCursor(
                current=URL(generator.generate_href(kind, artist_id)).joinpath("albums"),
                limit=20,
                offset=0,
            )
        )

    def test_response(self, generator: SpotifyPayloadGenerator):
        payload = generator.generate_artist()
        generator.add_artist_extended_properties(payload)
        generator.add_artist_albums(payload)

        model = SpotifyArtistCollection.model_validate(payload)

        self.assert_expected_name(model, payload)
        self.assert_expected_identifiers(model, payload)
        self.assert_expected_images(model, payload)
        self.assert_expected_genres(model, payload)
        self.assert_expected_followers(model, payload)
        self.assert_expected_popularity(model, payload)

        self.assert_has_all_items(model, payload["albums"]["items"], payload["albums"]["total"])
