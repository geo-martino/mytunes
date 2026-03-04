from abc import ABCMeta, abstractmethod
from datetime import date

import pytest
from faker import Faker
from pydantic import Json
from yarl import URL

from musify.models.item.genre import HasGenres
from musify.models.properties.length import HasLength
from musify.spotify import SpotifyResource
from musify.spotify.properties.followers import HasFollowers
from musify.spotify.properties.images import HasSpotifyImages
from musify.spotify.properties.popularity import HasPopularity
from musify.spotify.properties.uri import SpotifyUserURI
from tests.models.testers import UniqueKeyTester
from tests.spotify.generator import SpotifyPayloadGenerator


class SpotifyModelTester(UniqueKeyTester, metaclass=ABCMeta):

    @pytest.fixture(scope="class")
    def generator(self, faker: Faker) -> SpotifyPayloadGenerator:
        return SpotifyPayloadGenerator(faker)

    ################################################################################
    ## Response assertions
    ################################################################################
    @staticmethod
    def assert_expected_identifiers(model: SpotifyResource, payload: Json):
        assert model.uri == payload["uri"]
        assert model.uri.id == payload["id"]
        assert str(model.uri.public_url) == payload["external_urls"]["spotify"]
        assert str(model.uri.api_url) == payload["href"]

    @staticmethod
    def assert_expected_images(model: HasSpotifyImages, payload: Json):
        assert len(model.images) == 1

        max_height = max(img["height"] for img in payload["images"])
        expected = next(img for img in payload["images"] if img["height"] == max_height)

        result = next(iter(model.images.values()))
        assert str(result.url) == expected["url"]
        assert result.height == expected["height"]
        assert result.width == expected["width"]

    @staticmethod
    def assert_expected_length(model: HasLength, payload: Json):
        expected = payload["duration_ms"]
        if isinstance(expected, dict):
            expected = expected["totalMilliseconds"]

        assert int(model.length) == int(expected / 1000)

    @staticmethod
    def assert_expected_genres(model: HasGenres, payload: Json):
        assert sorted(genre.name for genre in model.genres) == sorted(payload["genres"])

    @staticmethod
    def assert_expected_followers(model: HasFollowers, payload: Json):
        assert model.followers == payload["followers"]["total"]

    @staticmethod
    def assert_expected_popularity(model: HasPopularity, payload: Json):
        assert model.popularity == payload["popularity"]


class SpotifyResourceTester(SpotifyModelTester, metaclass=ABCMeta):
    @staticmethod
    def test_spotify_user_uri_not_allowed(model: SpotifyResource, faker: Faker):
        additional_fields = model.model_dump(exclude={"uri"})

        uri = SpotifyUserURI(f"spotify:user:{faker.pystr()}")
        with pytest.raises(ValueError):
            model.__class__(**additional_fields, uri=uri)
