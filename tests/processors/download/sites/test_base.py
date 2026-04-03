import locale
from unittest.mock import patch, Mock, PropertyMock, MagicMock

import pytest
from faker import Faker
from pydantic import ValidationError
from yarl import URL

from musify.models.item.artist import Artist
from musify.models.item.track import Track
from musify.processors.clean.string import NameCleaner
from musify.processors.download.stores import AudioStore
from musify.processors.download.stores._base import HasLocale, GeneralAudioStore
from musify.processors.download.stores.exception import StoreError
from tests.models.testers import BaseModelTester
from tests.processors.download.utils import assert_value_in_url, assert_value_not_in_url


class TestAudioStore(BaseModelTester):
    @pytest.fixture
    @patch.multiple(
        AudioStore,
        __abstractmethods__=set(),
        _base_url=PropertyMock(return_value=URL.build(scheme="https", host="example.com")),
        _format_query_path_for_item=MagicMock(return_value=""),
        _format_query_params_for_item=MagicMock(return_value={}),
    )
    def model(self, faker: Faker) -> AudioStore:
        return AudioStore[str](
            name=faker.name(),
        )

    def test_format_fails(self, model: AudioStore, track: Track):
        with pytest.raises(ValidationError):
            model.format_search_url("unknown_type")

        model.fields = ()
        with pytest.raises(StoreError):
            model.format_search_url(track)

    @patch.multiple(
        AudioStore,
        __abstractmethods__=set(),
        _base_url=PropertyMock(return_value=URL.build(scheme="https", host="example.com")),
        _format_query_path_for_item=MagicMock(return_value=""),
        _format_query_params_for_item=MagicMock(side_effect=lambda item, query, *_, **__: {"q": query}),
    )
    def test_format_query_for_item_simple(
            self,
            model: AudioStore,
            track: Track,
            artist: Artist,
            faker: Faker,
    ):
        track.artists = [artist]

        result = model.format_search_url(track, fields=["name", "artists"])
        assert_value_in_url(result, track.name)
        assert_value_in_url(result, artist.name)

    @patch.multiple(
        AudioStore,
        __abstractmethods__=set(),
        _base_url=PropertyMock(return_value=URL.build(scheme="https", host="example.com")),
        _format_query_path_for_item=MagicMock(return_value=""),
        _format_query_params_for_item=MagicMock(side_effect=lambda item, query, *_, **__: {"q": query}),
    )
    def test_format_query_for_item_with_many_values(
            self,
            model: AudioStore,
            track: Track,
            artists: list[Artist],
            faker: Faker,
    ):
        track.artists = artists

        result = model.format_search_url(track, fields=["name", "artists"])
        assert_value_in_url(result, track.name)
        assert_value_in_url(result, track.artists[0].name)

        # only ever takes the first field when the singular name of a field is given
        # and many values are available for that field
        # e.g. only ever takes the first artist when multiple artists are present
        # and the requested field is just 'artist' not 'artists'
        assert_value_not_in_url(result, track.artist)

    @patch.multiple(
        AudioStore,
        __abstractmethods__=set(),
        _base_url=PropertyMock(return_value=URL.build(scheme="https", host="example.com")),
        _format_query_path_for_item=MagicMock(return_value=""),
        _format_query_params_for_item=MagicMock(side_effect=lambda item, query, *_, **__: {"q": query}),
    )
    def test_format_query_for_item_with_cleaner(
            self,
            model: AudioStore,
            track: Track,
            artists: list[Artist],
            faker: Faker,
    ):
        model.cleaner = NameCleaner()
        track.artists = artists

        result = model.format_search_url(track, fields=["name", "artists"])
        assert_value_in_url(result, model.cleaner.clean(track.name))
        assert_value_in_url(result, model.cleaner.clean(track.artists[0].name))


class TestHasLocale(BaseModelTester):
    @pytest.fixture
    def model(self, faker: Faker) -> HasLocale:
        return HasLocale()

    def test_validate_from_locale_alias(self):
        lc = HasLocale(locale="uk")
        assert lc.locale == locale.normalize("uk")

    def test_validate_from_locale_alias_fails(self):
        with pytest.raises(ValidationError):
            HasLocale(locale="unknown")


class TestGeneralAudioStore(BaseModelTester):
    @pytest.fixture
    def model(self):
        return GeneralAudioStore(url="https://example.com/search?q={}&type=t")

    def test_validate_urls(self):
        with pytest.raises(ValidationError, match="String should match pattern"):
            GeneralAudioStore(url="https://example.com/search?q={}&limit={}")

        with pytest.raises(ValidationError, match="Input should be a valid URL"):
            GeneralAudioStore(url="not_a_valid_url_with_placeholder_{}")
