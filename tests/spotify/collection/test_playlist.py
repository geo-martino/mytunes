import pytest
from faker import Faker
from yarl import URL

from musify.spotify.collection import SpotifyPageCursor
from musify.spotify.collection.playlist import SpotifyPlaylist
from tests.spotify.generator import SpotifyPayloadGenerator
from tests.spotify.testers import SpotifyResourceTester


class TestSpotifyPlaylist(SpotifyResourceTester):
    @pytest.fixture
    def model(self, generator: SpotifyPayloadGenerator, faker: Faker) -> SpotifyPlaylist:
        kind = "playlist"
        playlist_id = generator.generate_resource_id()

        return SpotifyPlaylist(
            name=faker.name(),
            owner=generator.generate_owner(),
            collaborative=faker.boolean(),
            uri=generator.generate_uri("playlist", playlist_id),
            total=faker.random_int(0, 200),
            cursor=SpotifyPageCursor(
                url=URL(generator.generate_href(kind, playlist_id)).joinpath("items"),
                limit=20,
                offset=0,
            )
        )

    def test_response(self, generator: SpotifyPayloadGenerator):
        payload = generator.generate_playlist()
        generator.add_playlist_items(payload)

        model = SpotifyPlaylist.model_validate(payload)

        self.assert_expected_name(model, payload)
        self.assert_expected_identifiers(model, payload)
        self.assert_expected_images(model, payload)
        self.assert_expected_followers(model, payload)

        self.assert_has_all_items(model, payload["items"]["items"], payload["items"]["total"])

        assert model.owner.uri == payload["owner"]["uri"]
        assert model.public is payload["public"]
        assert model.collaborative == payload["collaborative"]
