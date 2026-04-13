from abc import ABCMeta
from random import choice

import pytest
from faker import Faker
from mytunes._models.collection.playlist import Playlist
from mytunes._models.item.album import Album
from mytunes._models.item.artist import Artist
from mytunes._models.item.track import Track
# noinspection PyProtectedMember
from mytunes.spotify._properties.uri import SpotifyURIBase, SpotifyResourceURI, SpotifyUserURI
from pydantic import ValidationError
from tests.testers import BaseModelTester
from yarl import URL


class SpotifyURITester(BaseModelTester, metaclass=ABCMeta):
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
        return faker.pystr(22, 22)


class TestSpotifyURIBase(SpotifyURITester):
    @pytest.fixture
    def model(self, kind: str, id_value: str) -> SpotifyURIBase:
        uri_value = f"spotify:{kind}:{id_value}"
        return SpotifyURIBase(uri_value)

    def test_validate_uri_length(self, kind: str, id_value: str):
        with pytest.raises(ValidationError, match="Invalid Spotify URI format. Expected format"):  # too short
            SpotifyURIBase(f"spotify:{kind}")

        with pytest.raises(ValidationError, match="Invalid Spotify URI format. Expected format"):  # too long
            SpotifyURIBase(f"spotify:{kind}:{id_value}:extra")

    def test_properties(self, kind: str, id_value: str):
        uri = SpotifyURIBase(f"spotify:{kind}:{id_value}")
        assert uri.source == "spotify"
        assert uri.type == kind
        assert uri.id == id_value

    def test_from_id(self, kind: str, id_value: str):
        uri = SpotifyURIBase.from_id(id_value, kind=kind)
        assert uri.root == f"spotify:{kind}:{id_value}"

    def test_api_url(self, kind: str, id_value: str):
        uri = SpotifyURIBase(f"spotify:{kind}:{id_value}")
        assert uri.api_url == URL(f"https://api.spotify.com/v1/{kind}s/{id_value}")

    def test_from_api_url(self, kind: str, id_value: str):
        api_url = f"https://api.spotify.com/v1/{kind}s/{id_value}"
        uri = SpotifyURIBase(api_url)
        assert uri.type == kind
        assert uri.id == id_value

    def test_public_url(self, kind: str, id_value: str):
        uri = SpotifyURIBase(f"spotify:{kind}:{id_value}")
        assert uri.public_url == URL(f"https://open.spotify.com/{kind}/{id_value}")

    def test_from_public_url(self, kind: str, id_value: str):
        api_url = f"https://open.spotify.com/{kind}/{id_value}"
        uri = SpotifyURIBase(api_url)
        assert uri.type == kind
        assert uri.id == id_value


class TestSpotifyResourceURI(SpotifyURITester):
    @pytest.fixture
    def model(self, kind: str, id_value: str) -> SpotifyResourceURI:
        uri_value = f"spotify:{kind}:{id_value}"
        return SpotifyResourceURI(uri_value)

    def test_validate_id_length(self, kind: str, faker: Faker):
        with pytest.raises(ValidationError, match="Invalid Spotify URI format. ID must be"):  # too short
            SpotifyResourceURI(f"spotify:{kind}:{faker.pystr(23, 100)}")

        with pytest.raises(ValidationError, match="Invalid Spotify URI format. ID must be"):  # too long
            SpotifyResourceURI(f"spotify:{kind}:{faker.pystr(1, 21)}")

    def test_validate_type_is_not_user(self, id_value: str, faker: Faker):
        with pytest.raises(ValidationError, match="Spotify user URIs are not allowed"):
            SpotifyResourceURI(f"spotify:user:{id_value}")


class TestSpotifyUserURI(SpotifyURITester):
    @pytest.fixture
    def model(self, kind: str, id_value: str) -> SpotifyUserURI:
        uri_value = f"spotify:user:{id_value}"
        return SpotifyUserURI(uri_value)

    @pytest.fixture
    def id_value(self, faker: Faker) -> str:
        return faker.pystr()

    def test_validate_type_is_user(self, id_value: str, kind: str, faker: Faker):
        with pytest.raises(ValidationError, match="Only Spotify user URIs are allowed"):
            SpotifyUserURI(f"spotify:{kind}:{id_value}")
