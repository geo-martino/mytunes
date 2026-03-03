from random import choice

import pytest
from faker import Faker
from yarl import URL

from musify.models.collection.playlist import Playlist
from musify.models.item.album import Album
from musify.models.item.artist import Artist
from musify.models.item.track import Track
from musify.spotify.properties.uri import SpotifyURI
from tests.models.testers import MusifyModelTester


class TestSpotifyURI(MusifyModelTester):
    @pytest.fixture
    def model(self, kind: str, id_value: str) -> SpotifyURI:
        uri_value = f"spotify:{kind}:{id_value}"
        return SpotifyURI(uri_value)

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

    def test_validate_uri_length(self, kind: str, id_value: str):
        with pytest.raises(ValueError, match="Invalid Spotify URI format. Expected format"):  # too short
            SpotifyURI(f"spotify:{kind}")

        with pytest.raises(ValueError, match="Invalid Spotify URI format. Expected format"):  # too long
            SpotifyURI(f"spotify:{kind}:{id_value}:extra")

    def test_validate_id_length(self, kind: str, faker: Faker):
        with pytest.raises(ValueError, match="Invalid Spotify URI format. ID must be"):  # too short
            SpotifyURI(f"spotify:{kind}:{"".join(faker.random_letters(30))}")

        with pytest.raises(ValueError, match="Invalid Spotify URI format. ID must be"):  # too long
            SpotifyURI(f"spotify:{kind}:{"".join(faker.random_letters(10))}")

    def test_properties(self, kind: str, id_value: str):
        uri = SpotifyURI(f"spotify:{kind}:{id_value}")
        assert uri.source == "spotify"
        assert uri.type == kind
        assert uri.id == id_value

    def test_from_id(self, kind: str, id_value: str):
        uri = SpotifyURI.from_id(id_value, kind=kind)
        assert uri.root == f"spotify:{kind}:{id_value}"

    def test_api_url(self, kind: str, id_value: str):
        uri = SpotifyURI(f"spotify:{kind}:{id_value}")
        assert uri.api_url == URL(f"https://api.spotify.com/v1/{kind}s/{id_value}")

    def test_from_api_url(self, kind: str, id_value: str):
        api_url = f"https://api.spotify.com/v1/{kind}s/{id_value}"
        uri = SpotifyURI(api_url)
        assert uri.type == kind
        assert uri.id == id_value

    def test_public_url(self, kind: str, id_value: str):
        uri = SpotifyURI(f"spotify:{kind}:{id_value}")
        assert uri.public_url == URL(f"https://open.spotify.com/{kind}/{id_value}")

    def test_from_public_url(self, kind: str, id_value: str):
        api_url = f"https://open.spotify.com/{kind}/{id_value}"
        uri = SpotifyURI(api_url)
        assert uri.type == kind
        assert uri.id == id_value
