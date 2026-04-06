import pytest
from faker import Faker
from pydantic import ValidationError

from musify.spotify._properties.uri import SpotifyUserURI, SpotifyResourceURI
from musify.spotify.user import SpotifyUser
from tests.spotify.generator import SpotifyPayloadGenerator
from tests.spotify.testers import SpotifyModelTester
from tests.testers import UniqueKeyTester


class TestSpotifyUser(UniqueKeyTester, SpotifyModelTester):
    @pytest.fixture
    def model(self, resource_id: str, faker: Faker) -> SpotifyUser:
        return SpotifyUser(
            name=faker.name(),
            email=faker.email(),
            uri=SpotifyUserURI.from_id(resource_id, kind="user"),
        )

    @pytest.fixture
    def resource_id(self, faker: Faker) -> str:
        return faker.pystr()  # override to return variable lengths

    def test_non_spotify_user_uri_not_allowed(self, model: SpotifyUser, faker: Faker):
        additional_fields = model.model_dump(exclude={"uri"})

        uri = SpotifyResourceURI(f"spotify:artist:{faker.pystr(22, 22)}")
        with pytest.raises(ValidationError):
            SpotifyUser(**additional_fields, uri=uri)

    def test_response(self, generator: SpotifyPayloadGenerator):
        payload = generator.generate_user()
        model = SpotifyUser.model_validate(payload)

        self.assert_expected_identifiers(model, payload)
        self.assert_expected_images(model, payload)
        self.assert_expected_followers(model, payload)

        assert model.name == payload["display_name"]
        if "email" in payload:
            assert model.email == payload["email"]
