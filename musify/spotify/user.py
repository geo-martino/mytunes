import pytest
from faker import Faker

from musify.spotify.properties.uri import SpotifyUserURI, SpotifyResourceURI
from tests.models.testers import UniqueKeyTester
from tests.spotify.test_user import SpotifyUser


class TestSpotifyUser(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> SpotifyUser:
        return SpotifyUser(
            uri=SpotifyUserURI(f"spotify:user:{"_".join(faker.words())}"),
        )

    def test_non_spotify_user_uri_not_allowed(self, model: SpotifyUser, faker: Faker):
        additional_fields = model.model_dump(exclude={"uri"})

        uri = SpotifyResourceURI(f"spotify:artist:{"".join(faker.random_letters(22))}")
        with pytest.raises(ValueError):
            SpotifyUser(**additional_fields, uri=uri)
