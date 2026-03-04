from random import choice

import pytest
from faker import Faker
from yarl import URL

from musify.models.collection.playlist import Playlist
from musify.models.item.album import Album
from musify.models.item.artist import Artist
from musify.models.item.track import Track
# noinspection PyProtectedMember
from musify.spotify.properties.uri import _SpotifyURIBase, SpotifyResourceURI, SpotifyUserURI
from tests.models.testers import MusifyModelTester


class SpotifyURITester(MusifyModelTester):
    @pytest.fixture
    def kind(self) -> str:
        types = (
            Track.type,
            Album.type,
            Artist.type,
            Playlist.type,
        )
        return choice(types)

    @pytest.fixture
    def id_value(self, faker: Faker) -> str:
        return "".join(faker.random_letters(22))


class TestSpotifyURIBase(SpotifyURITester):
    @pytest.fixture
    def model(self, kind: str, id_value: str) -> _SpotifyURIBase:
        uri_value = f"spotify:{kind}:{id_value}"
        return _SpotifyURIBase(uri_value)

    def test_validate_uri_length(self, kind: str, id_value: str):
        with pytest.raises(ValueError, match="Invalid Spotify URI format. Expected format"):  # too short
            _SpotifyURIBase(f"spotify:{kind}")

        with pytest.raises(ValueError, match="Invalid Spotify URI format. Expected format"):  # too long
            _SpotifyURIBase(f"spotify:{kind}:{id_value}:extra")

    def test_properties(self, kind: str, id_value: str):
        uri = _SpotifyURIBase(f"spotify:{kind}:{id_value}")
        assert uri.source == "spotify"
        assert uri.type == kind
        assert uri.id == id_value

    def test_from_id(self, kind: str, id_value: str):
        uri = _SpotifyURIBase.from_id(id_value, kind=kind)
        assert uri.root == f"spotify:{kind}:{id_value}"

    def test_api_url(self, kind: str, id_value: str):
        uri = _SpotifyURIBase(f"spotify:{kind}:{id_value}")
        assert uri.api_url == URL(f"https://api.spotify.com/v1/{kind}s/{id_value}")

    def test_from_api_url(self, kind: str, id_value: str):
        api_url = f"https://api.spotify.com/v1/{kind}s/{id_value}"
        uri = _SpotifyURIBase(api_url)
        assert uri.type == kind
        assert uri.id == id_value

    def test_public_url(self, kind: str, id_value: str):
        uri = _SpotifyURIBase(f"spotify:{kind}:{id_value}")
        assert uri.public_url == URL(f"https://open.spotify.com/{kind}/{id_value}")

    def test_from_public_url(self, kind: str, id_value: str):
        api_url = f"https://open.spotify.com/{kind}/{id_value}"
        uri = _SpotifyURIBase(api_url)
        assert uri.type == kind
        assert uri.id == id_value


class TestSpotifyResourceURI(MusifyModelTester):
    @pytest.fixture
    def model(self, kind: str, id_value: str) -> SpotifyResourceURI:
        uri_value = f"spotify:{kind}:{id_value}"
        return SpotifyResourceURI(uri_value)

    @pytest.fixture
    def kind(self) -> str:
        types = (
            Track.type,
            Album.type,
            Artist.type,
            Playlist.type,
        )
        return choice(types)

    @pytest.fixture
    def id_value(self, faker: Faker) -> str:
        return "".join(faker.random_letters(22))

    def test_validate_id_length(self, kind: str, faker: Faker):
        with pytest.raises(ValueError, match="Invalid Spotify URI format. ID must be"):  # too short
            SpotifyResourceURI(f"spotify:{kind}:{"".join(faker.random_letters(30))}")

        with pytest.raises(ValueError, match="Invalid Spotify URI format. ID must be"):  # too long
            SpotifyResourceURI(f"spotify:{kind}:{"".join(faker.random_letters(10))}")

    def test_validate_type_is_not_user(self, id_value: str, faker: Faker):
        with pytest.raises(ValueError, match="Spotify user URIs are not allowed"):
            SpotifyResourceURI(f"spotify:user:{id_value}")


class TestSpotifyUserURI(SpotifyURITester):
    @pytest.fixture
    def model(self, kind: str, id_value: str) -> SpotifyUserURI:
        uri_value = f"spotify:user:{id_value}"
        return SpotifyUserURI(uri_value)

    @pytest.fixture
    def id_value(self, faker: Faker) -> str:
        length = faker.random_int(10, 50)
        return "".join(faker.random_letters(length))

    def test_validate_type_is_user(self, id_value: str, kind:str, faker: Faker):
        with pytest.raises(ValueError, match="Only Spotify user URIs are allowed"):
            SpotifyUserURI(f"spotify:{kind}:{id_value}")
