import pytest
from faker import Faker
from yarl import URL

from musify.spotify.collection._base import SpotifyItemsCursor
from musify.spotify.collection.album import SpotifyAlbumCollection
from tests.spotify.generator import SpotifyPayloadGenerator
from tests.spotify.testers import SpotifyResourceTester


class TestSpotifyAlbumCollection(SpotifyResourceTester):
    @pytest.fixture
    def model(self, generator: SpotifyPayloadGenerator, faker: Faker) -> SpotifyAlbumCollection:
        kind = "album"
        album_id = generator.generate_resource_id()

        return SpotifyAlbumCollection(
            name=faker.name(),
            popularity=faker.random_int(0, 100),
            uri=generator.generate_uri(kind, album_id),
            total=faker.random_int(1, 20),
            cursor=SpotifyItemsCursor(
                current=URL(generator.generate_href(kind, album_id)).joinpath("tracks"),
                limit=20,
                offset=0,
            )
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
