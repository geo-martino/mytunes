from abc import ABCMeta
from collections.abc import Collection

import pytest
from faker import Faker
from pydantic import Json, ValidationError

from mytunes._models.collection import RemoteCollection
from mytunes._models.item.artist import HasArtists
from mytunes._models.item.genre import HasGenres
from mytunes._models.properties.image import HasImages
from mytunes._models.properties.length import HasLength
from mytunes._models.properties.name import HasName
from mytunes._models.properties.uri import HasURI
from mytunes.spotify import SpotifyResource
from mytunes.spotify._properties.rating import HasSpotifyRating
from mytunes.spotify._properties.stats import HasFollowers
from mytunes.spotify._properties.uri import SpotifyUserURI
from tests.testers import UniqueKeyTester, BaseModelTester


class SpotifyModelTester(BaseModelTester, metaclass=ABCMeta):

    ################################################################################
    ## Response assertions
    ################################################################################
    @staticmethod
    def assert_expected_name(model: HasName, payload: Json):
        assert model.name == payload["name"]

    @staticmethod
    def assert_expected_identifiers(model: HasURI, payload: Json):
        assert model.uri == payload["uri"]
        assert model.uri.id == payload["id"]
        assert str(model.uri.public_url) == payload["external_urls"]["spotify"]
        assert str(model.uri.api_url) == payload["href"]

    @staticmethod
    def assert_expected_images(model: HasImages, payload: Json):
        assert len(model.images) == 1

        max_height = max(img["height"] for img in payload["images"])
        expected = next(img for img in payload["images"] if img["height"] == max_height)

        result = next(iter(model.images.values()))
        assert str(result.url) == expected["url"]
        assert result.height == expected["height"]
        assert result.width == expected["width"]

    @staticmethod
    def assert_expected_artists(model: HasArtists, payload: Json):
        actual = sorted(artist.name for artist in model.artists)
        expected = sorted(artist["name"] for artist in payload["artists"])
        assert actual == expected

    @staticmethod
    def assert_expected_genres(model: HasGenres, payload: Json):
        assert sorted(genre.name for genre in model.genres) == sorted(payload["genres"])

    @staticmethod
    def assert_expected_length(model: HasLength, payload: Json):
        expected = payload["duration_ms"]
        if isinstance(expected, dict):
            expected = expected["totalMilliseconds"]

        assert int(model.length) == int(expected / 1000)

    @staticmethod
    def assert_expected_followers(model: HasFollowers, payload: Json):
        assert model.followers == payload["followers"]["total"]

    @staticmethod
    def assert_expected_rating(model: HasSpotifyRating, payload: Json):
        assert model.rating is not None
        assert int(model.rating) == payload["popularity"]

    @staticmethod
    def assert_has_all_items(model: RemoteCollection, items: Collection, total: int):
        if len(items) == total:
            assert model.has_all_items
        else:
            assert not model.has_all_items


class SpotifyResourceTester(UniqueKeyTester, SpotifyModelTester, metaclass=ABCMeta):
    @staticmethod
    def test_spotify_user_uri_not_allowed(model: SpotifyResource, faker: Faker):
        additional_fields = model.model_dump(exclude={"uri"})

        uri = SpotifyUserURI(f"spotify:user:{faker.pystr()}")
        with pytest.raises(ValidationError):
            model.__class__(**additional_fields, uri=uri)
