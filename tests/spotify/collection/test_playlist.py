import pytest
from faker import Faker
from pydantic import ValidationError
from yarl import URL

from musify._models._context import RemoteModelContext
from musify.spotify._collection.playlist import SpotifyPlaylist, SpotifyMutablePlaylist
from musify.spotify.cursors import SpotifyIndexCursor
from musify.spotify.user import SpotifyUser
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
            uri=generator.generate_uri("playlist", playlist_id),
            total=faker.random_int(0, 200),
            cursor=SpotifyIndexCursor(
                url=URL(generator.generate_href(kind, playlist_id)).joinpath("items"),
                limit=20,
                offset=0,
                total=faker.random_int(),
            )
        )

    def test_response(self, generator: SpotifyPayloadGenerator):
        payload = generator.generate_playlist()
        generator.add_playlist_items(payload)

        if not payload["collaborative"]:
            model = SpotifyPlaylist.model_validate(payload)
        else:
            model = SpotifyMutablePlaylist.model_validate(payload)

        self.assert_expected_name(model, payload)
        self.assert_expected_identifiers(model, payload)
        self.assert_expected_images(model, payload)
        self.assert_expected_followers(model, payload)

        self.assert_has_all_items(model, payload["items"]["items"], payload["items"]["total"])

        assert model.owner.uri == payload["owner"]["uri"]
        assert model.public is payload["public"]
        assert model.collaborative == payload["collaborative"]

    def test_validate_mutability(self, model: SpotifyPlaylist, generator: SpotifyPayloadGenerator):
        context = RemoteModelContext(user=model.owner)
        # not collaborative and user is the owner, implies mutable
        with pytest.raises(ValidationError, match="implies that this playlist is mutable"):
            SpotifyPlaylist.model_validate(model, context=context)

    def test_validate_immutability(self, model: SpotifyPlaylist, generator: SpotifyPayloadGenerator):
        user = SpotifyUser.model_validate(generator.generate_user())
        context = RemoteModelContext(user=user)

        # not collaborative and user is not the owner, implies immutable
        assert model == SpotifyPlaylist.model_validate(model, context=context)


class TestSpotifyMutablePlaylist(SpotifyResourceTester):
    @pytest.fixture
    def model(self, generator: SpotifyPayloadGenerator, faker: Faker) -> SpotifyPlaylist:
        kind = "playlist"
        playlist_id = generator.generate_resource_id()

        return SpotifyMutablePlaylist(
            name=faker.name(),
            owner=generator.generate_owner(),
            collaborative=faker.boolean(),
            uri=generator.generate_uri("playlist", playlist_id),
            total=faker.random_int(0, 200),
            cursor=SpotifyIndexCursor(
                url=URL(generator.generate_href(kind, playlist_id)).joinpath("items"),
                limit=20,
                offset=0,
                total=faker.random_int(),
            )
        )

    def test_validate_mutability_on_owner(
            self, model: SpotifyMutablePlaylist, generator: SpotifyPayloadGenerator
    ):
        # not collaborative and user is the owner, implies mutable
        context = RemoteModelContext(user=model.owner)
        model.collaborative = False
        assert model == SpotifyMutablePlaylist.model_validate(model, context=context)

    def test_validate_mutability_on_collaborative(
            self, model: SpotifyMutablePlaylist, generator: SpotifyPayloadGenerator
    ):
        # is collaborative and user is not the owner, implies mutable
        user = SpotifyUser.model_validate(generator.generate_user())
        context = RemoteModelContext(user=user)
        model.collaborative = True
        assert model == SpotifyMutablePlaylist.model_validate(model, context=context)

    def test_validate_immutability(self, model: SpotifyMutablePlaylist, generator: SpotifyPayloadGenerator):
        user = SpotifyUser.model_validate(generator.generate_user())
        context = RemoteModelContext(user=user)
        model.collaborative = False

        # not collaborative and user is not the owner, implies immutable
        with pytest.raises(ValidationError, match="implies that this playlist is immutable"):
            SpotifyMutablePlaylist.model_validate(model, context=context)
