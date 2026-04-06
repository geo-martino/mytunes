from unittest.mock import patch

import pytest
from faker import Faker
from yarl import URL

from musify.spotify._api import SpotifyAPI
from musify.spotify._api.artist import SpotifyArtistEndpoints, _ALL_ALBUM_TYPES
from musify.spotify._collection.artist import SpotifyArtistCollection
from musify.spotify.cursors import SpotifyIndexCursor
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
            cursor=SpotifyIndexCursor(
                url=URL(generator.generate_href(kind, artist_id)).joinpath("albums"),
                limit=20,
                offset=0,
                total=faker.random_int(),
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
        self.assert_expected_rating(model, payload)

        self.assert_has_all_items(model, payload["albums"]["items"], payload["albums"]["total"])

    async def test_reload_items(self, model: SpotifyArtistCollection, api: SpotifyAPI):
        with patch.object(SpotifyArtistEndpoints, "get_all", return_value=()) as mock_get_all:
            await model.reload_items(api)

            called_album_types = {t for call in mock_get_all.call_args_list for t in call.kwargs["types"]}
            assert called_album_types == set(_ALL_ALBUM_TYPES)
