from abc import ABCMeta
from random import choice
from unittest.mock import patch, Mock, MagicMock

import pytest
from faker import Faker
from pydantic import InstanceOf
from pytest_mock import MockerFixture

from mytunes._models.item.track import Track
from mytunes.processors.score.string import StringScorer, StringScoreReducer, KaraokeScorer, NameScorer, \
    ArtistScorer, \
    AlbumScorer
from tests.testers import BaseModelTester


class StringScorerTester(BaseModelTester, metaclass=ABCMeta):
    @staticmethod
    def test_calculate_score_returns_on_missing_values(model: StringScorer):
        assert model._calculate_score("", "other value") == 0
        assert model._calculate_score("test value", "") == 0


class StringScoreReducerTester(BaseModelTester, metaclass=ABCMeta):
    @staticmethod
    def test_reduce_score_is_called(model: StringScorer, mocker: MockerFixture):
        mock_reduce_score = mocker.spy(model, "_reduce_score")
        model._calculate_score("test value", "other value")
        mock_reduce_score.assert_called_once()


class TestStringScoreReducer(BaseModelTester):
    @pytest.fixture
    @patch.multiple(
        StringScoreReducer,
        __abstractmethods__=set(),
        _calculate_score=MagicMock(),
    )
    def model(self) -> StringScoreReducer:
        return StringScoreReducer[InstanceOf[Mock]](type="test", cleaner=Mock())

    def test_reduce_score_skips(self, model: StringScoreReducer, faker: Faker):
        score = faker.random_int()
        assert model._reduce_score(score=score, value="", other="other value") == score
        assert model._reduce_score(score=score, value="test value", other=None) == score

        model.reduce_on_phrases = set()
        model.reduce_factor = 0.5
        assert model._reduce_score(score=score, value="test value", other="other value") == score

        model.reduce_factor = 0.5
        assert model._reduce_score(score=0, value="test value", other="other value") == 0

    def test_reduce_score(self, model: StringScoreReducer, faker: Faker):
        model.reduce_factor = faker.random_int(0, 99) / 100
        model.reduce_on_phrases = {"other"}

        score = faker.random_int()
        expected = round(score * model.reduce_factor, 2)

        # reduce phrases not found in either value
        assert model._reduce_score(score=score, value="test value", other="another test value") == score

        reduced_score = model._reduce_score(score=score, value="test value", other="other value")
        assert round(reduced_score, 2) == expected

        reduced_score = model._reduce_score(score=score, value="other value", other="test value")
        assert round(reduced_score, 2) == expected


class TestKaraokeScorer(StringScorerTester):
    @pytest.fixture
    def model(self, faker: Faker) -> KaraokeScorer:
        return KaraokeScorer(weight=faker.random_int())

    # noinspection PyMethodOverriding
    @staticmethod
    def test_calculate_score_returns_on_missing_values(model: KaraokeScorer, faker: Faker):
        assert model._calculate_score(None, None) is False
        assert model._calculate_score(None, "") is False

    def test_calculate_score(self, model: KaraokeScorer):
        model.karaoke_phrases = {"karaoke", "backing", "instrumental"}

        assert model._calculate_score(None, "test value") is False
        assert model._calculate_score(None, f"test {choice(list(model.karaoke_phrases))}") is True

    def test_score_on_prefer_not_karaoke(self, model: KaraokeScorer, track: Track):
        model.karaoke_phrases = {"karaoke", "backing", "instrumental"}
        model.prefer_not_karaoke = True

        assert model.score(track) == 1 * model.weight

        track.artist = f"test artist {choice(list(model.karaoke_phrases))}"
        assert model.score(track) == 0

    def test_score_on_prefer_karaoke(self, model: KaraokeScorer, track: Track, faker: Faker):
        model.karaoke_phrases = {"karaoke", "backing", "instrumental"}
        model.prefer_not_karaoke = False

        assert model.score(track) == 0

        track.artist = f"test artist {choice(list(model.karaoke_phrases))}"
        assert model.score(track) == 1 * model.weight


class TestNameScorer(StringScorerTester, StringScoreReducerTester):
    @pytest.fixture
    def model(self) -> NameScorer:
        return NameScorer()

    def test_calculate_score(self, model: NameScorer):
        assert model._calculate_score("test title", "test title") == 1
        assert model._calculate_score("test title", "other title") == 0.5
        assert model._calculate_score("this is a title", "this is another title") == 0.75

        assert model._calculate_score("a different title", "this is a different title") == 1
        assert model._calculate_score("this is a different title", "a different title") == 0.6


class TestArtistScorer(StringScorerTester):
    @pytest.fixture
    def model(self) -> ArtistScorer:
        return ArtistScorer(scale_on_many_artists=False)

    def test_calculate_score_simple(self, model: ArtistScorer):
        model.scale_on_many_artists = False

        artists_1 = ["artist 1", "artist 2", "artist 3"]
        artists_2 = ["artist 1", "artist 2", "artist 3"]
        assert model._calculate_score(artists_1, artists_2) == 1

        # matches 1/2 words from each artist
        artists_1 = ["artist 1", "artist 2", "artist 3"]
        artists_2 = ["artist"]
        assert model._calculate_score(artists_1, artists_2) == 0.5

    def test_calculate_score_complex(self, model: ArtistScorer):
        model.scale_on_many_artists = False

        artists_1 = ["band", "a singer", "artist"]
        artists_2 = ["artist", "singer", "other"]
        assert model._calculate_score(artists_1, artists_2) == 0.5

    def test_calculate_score_with_scaling_basic(self, model: ArtistScorer):
        model.scale_on_many_artists = True

        artists_1 = ["artist", "nope", "other"]
        artists_2 = ["band", "a singer", "artist"]
        assert round(model._calculate_score(artists_1, artists_2), 2) == 0.33

        artists_1 = ["nope", "other", "artist"]
        assert round(model._calculate_score(artists_1, artists_2), 2) == 0.11

    def test_calculate_score_with_scaling_complex(self, model: ArtistScorer):
        model.scale_on_many_artists = True

        artists_1 = ["band", "a singer", "artist"]
        artists_2 = ["artist", "singer", "other"]
        assert round(model._calculate_score(artists_1, artists_2), 2) == 0.19

        artists_1 = ["band", "artist", "a singer"]
        assert round(model._calculate_score(artists_1, artists_2), 2) == 0.22


class TestAlbumScorer(StringScorerTester, StringScoreReducerTester):
    @pytest.fixture
    def model(self) -> AlbumScorer:
        return AlbumScorer()

    def test_calculate_score(self, model: NameScorer):
        assert model._calculate_score("album name", "name") == 0.5
        assert model._calculate_score("name", "album name") == 1
        assert model._calculate_score("brand new album", "this is a brand new really cool album") == 1
