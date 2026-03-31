import locale
from unittest.mock import patch, Mock, PropertyMock
from urllib.parse import unquote

import pytest
from faker import Faker
from pydantic import ValidationError
from yarl import URL

from musify.models.item.artist import Artist
from musify.models.item.track import Track
from musify.processors.clean.string import NameCleaner
from musify.processors.download.sites import AudioStore
from musify.processors.download.sites._base import HasLocale
from musify.processors.download.sites.exception import StoreError
from tests.models.testers import BaseModelTester


class TestAudioStore(BaseModelTester):
    @pytest.fixture
    @patch.multiple(
        AudioStore,
        __abstractmethods__=set(),
        _base_url=PropertyMock(return_value=URL.build(scheme="https", host="example.com")),
        _format_query_path_for_item=Mock(return_value=""),
        _format_query_params_for_item=Mock(return_value={}),
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
        _format_query_path_for_item=Mock(return_value=""),
        _format_query_params_for_item=Mock(side_effect=lambda item, query, *_, **__: {"q": query}),
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
        query_values = [unquote(value) for value in result.query.values()]

        assert any(track.name in value for value in query_values)
        assert any(artist.name in value for value in query_values)

    @patch.multiple(
        AudioStore,
        __abstractmethods__=set(),
        _base_url=PropertyMock(return_value=URL.build(scheme="https", host="example.com")),
        _format_query_path_for_item=Mock(return_value=""),
        _format_query_params_for_item=Mock(side_effect=lambda item, query, *_, **__: {"q": query}),
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
        query_values = [unquote(value) for value in result.query.values()]

        assert any(track.name in value for value in query_values)
        assert any(track.artists[0].name in value for value in query_values)

        # only ever takes the first field when the singular name of a field is given
        # and many values are available for that field
        # e.g. only ever takes the first artist when multiple artists are present
        # and the requested field is just 'artist' not 'artists'
        assert all(track.artist not in value for value in query_values)

    @patch.multiple(
        AudioStore,
        __abstractmethods__=set(),
        _base_url=PropertyMock(return_value=URL.build(scheme="https", host="example.com")),
        _format_query_path_for_item=Mock(return_value=""),
        _format_query_params_for_item=Mock(side_effect=lambda item, query, *_, **__: {"q": query}),
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
        query_values = [unquote(value) for value in result.query.values()]

        name = model.cleaner.clean(track.name)
        assert any(name in unquote(value) for value in query_values)
        artist_name = model.cleaner.clean(track.artists[0].name)
        assert any(artist_name in unquote(value) for value in query_values)


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
