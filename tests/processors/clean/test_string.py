from abc import ABCMeta
from unittest.mock import patch, MagicMock

import pytest

from musify.exception import MusifyTypeError
from musify.models.item.album import HasAlbum
from musify.models.item.artist import HasArtists, Artist
from musify.models.properties.name import HasName
from musify.processors.clean.string import StringCleaner, NameCleaner, ArtistCleaner, AlbumCleaner
from tests.models.testers import BaseModelTester


class StringCleanerTester(BaseModelTester, metaclass=ABCMeta):
    @staticmethod
    def test_get_item_value_basic(model: StringCleaner):
        item = "Test Name"
        assert model._get_item_value(item) == item

    @staticmethod
    def test_get_item_value_returns_on_missing_value(model: StringCleaner):
        assert model._get_item_value(None) == ""

    @staticmethod
    def test_get_item_value_fails(model: StringCleaner):
        with pytest.raises(MusifyTypeError):
            model._get_item_value(123)


class TestStringCleaner(StringCleanerTester):
    @pytest.fixture
    @patch.multiple(
        StringCleaner,
        __abstractmethods__=set(),
        _get_item_value=MagicMock(),
    )
    def model(self) -> StringCleaner:
        return StringCleaner(
            drop_brackets=False,
            drop_non_alphanumeric=False,
        )

    def test_clean_returns_on_missing_value(self, model: StringCleaner):
        assert model.clean(None) == ""

    def test_split_on(self, model: StringCleaner):
        model.split_on = {"feat.", "ft."}

        assert model.clean("Song Title feat. Artist") == "song title"
        assert model.clean("Song Title ft. Artist") == "song title"

    def test_drop_brackets(self, model: StringCleaner):
        model.drop_brackets = True

        assert model.clean("Song Title (Live)") == "song title"
        assert model.clean("Song Title [Remix]") == "song title"

    def test_drop_non_alphanumeric(self, model: StringCleaner):
        model.drop_non_alphanumeric = True

        assert model.clean("Song Title! @2024") == "song title 2024"
        assert model.clean("Artist's Name") == "artist's name"

    def test_drop_phrases(self, model: StringCleaner):
        model.drop_phrases = {"remix", "live"}

        assert model.clean("Song Title live at wembley") == "song title at wembley"
        assert model.clean("Song Title remix ") == "song title"
        assert model.clean("Song Title - remixed") == "song title - remixed"


class TestNameCleaner(StringCleanerTester):
    @pytest.fixture
    def model(self) -> NameCleaner:
        return NameCleaner(
            drop_brackets=False,
            drop_non_alphanumeric=False,
        )

    def test_get_item_value(self, model: NameCleaner):
        item = HasName(name="Test Name")

        assert model._get_item_value(item) == item.name
        assert model._get_item_value(item.name) == item.name


class TestArtistCleaner(StringCleanerTester):
    @pytest.fixture
    def model(self) -> ArtistCleaner:
        return ArtistCleaner(
            drop_brackets=False,
            drop_non_alphanumeric=False,
        )

    def test_clean(self, model: ArtistCleaner):
        artist_names = ["Artist One", "Artist Two", "Artist Three"]
        item = HasArtists()
        item.artists = artist_names

        assert model.clean(item) == ["artist one", "artist two", "artist three"]
        assert model.clean(item.artists) == ["artist one", "artist two", "artist three"]
        assert model.clean(artist_names) == ["artist one", "artist two", "artist three"]

        assert model.clean(item.artists[0]) == ["artist one"]
        assert model.clean(artist_names[0]) == ["artist one"]

    def test_get_item_value(self, model: NameCleaner):
        item = Artist(name="Test Name")

        assert model._get_item_value(item) == item.name
        assert model._get_item_value(item.name) == item.name


class TestAlbumCleaner(StringCleanerTester):
    @pytest.fixture
    def model(self) -> AlbumCleaner:
        return AlbumCleaner(
            drop_brackets=False,
            drop_non_alphanumeric=False,
        )

    def test_get_item_value(self, model: NameCleaner):
        item = HasAlbum()
        assert model._get_item_value(item) == ""

        item.album = "Test Album"
        assert model._get_item_value(item) == item.album.name
        assert model._get_item_value(item.album) == item.album.name
        assert model._get_item_value(item.album.name) == item.album.name
