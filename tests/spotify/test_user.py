import pytest
from faker import Faker
from pydantic import Json
from yarl import URL

from musify.spotify.properties.uri import SpotifyUserURI, SpotifyResourceURI
from musify.spotify.user import SpotifyUser
from tests.models.testers import UniqueKeyTester
from tests.spotify.utils import generate_images


class TestSpotifyUser(UniqueKeyTester):
    @pytest.fixture
    def model(self, faker: Faker) -> SpotifyUser:
        return SpotifyUser(
            name=faker.name(),
            email=faker.email(),
            followers=faker.random_int(),
            uri=SpotifyUserURI(f"spotify:user:{"_".join(faker.words())}"),
        )

    @pytest.fixture
    def payload(self, faker: Faker) -> Json:
        user_id = faker.pystr()
        return {
            "country": faker.country_code(representation="alpha-2"),
            "display_name": faker.name(),
            "email": faker.email(),
            "explicit_content": {
                "filter_enabled": faker.boolean(),
                "filter_locked": faker.boolean()
            },
            "external_urls": {
                "spotify": str(URL.build(
                    scheme="https", host="open.spotify.com", path=f"/user/{user_id}"
                ))
            },
            "followers": {
                "href": None,
                "total": faker.random_int(),
            },
            "href": str(URL.build(
                scheme="https", host="api.spotify.com", path=f"/v1/users/{user_id}"
            )),
            "id": user_id,
            "images": generate_images(faker),
            "product": faker.random_element(("premium", "free", "open")),
            "type": "user",
            "uri": f"spotify:user:{user_id}",
        }

    def test_non_spotify_user_uri_not_allowed(self, model: SpotifyUser, faker: Faker):
        additional_fields = model.model_dump(exclude={"uri"})

        uri = SpotifyResourceURI(f"spotify:artist:{faker.pystr(22, 22)}")
        with pytest.raises(ValueError):
            SpotifyUser(**additional_fields, uri=uri)

    def test_response(self, payload: Json):
        user = SpotifyUser.model_validate(payload)

        assert user.name == payload["display_name"]
        assert user.email == payload["email"]
        assert user.followers == payload["followers"]["total"]

        assert len(user.images) == 1
        assert str(next(iter(user.images.values())).url) == payload["images"][0]["url"]

        assert user.uri == payload["uri"]
        assert user.uri.id == payload["id"]
        assert str(user.uri.public_url) == payload["external_urls"]["spotify"]
        assert str(user.uri.api_url) == payload["href"]
