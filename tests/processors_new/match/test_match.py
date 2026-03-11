from copy import copy
from random import sample, choice
from unittest.mock import patch

import pytest
from faker import Faker

from musify.models.collection.album import AlbumCollection
from musify.models.item.album import HasAlbums, Album
from musify.models.item.artist import HasArtists, Artist
from musify.models.item.track import Track
from musify.models.properties.date import HasReleaseDate
from musify.models.properties.length import HasLength
from musify.models.properties.name import HasName
from musify.processors_new.match import Matcher
from musify.processors_new.match.score import Scorer
from musify.processors_new.match.score.numeric import NumericScorer, LengthScorer, ReleaseYearScorer
from musify.processors_new.match.score.string import StringScorer, NameScorer, ArtistScorer, AlbumScorer
from tests.models.testers import BaseModelTester


class TestMatcher(BaseModelTester):
    @pytest.fixture
    def model(self, scorers: list[Scorer]) -> Matcher:
        return Matcher(scorers=scorers)

    @pytest.fixture
    def scorers(self) -> list[Scorer]:
        """Fixture for providing a list of scorers to test the Matcher model with."""
        return [
            NameScorer(),
            ArtistScorer(scale_on_many_artists=False),
            AlbumScorer(),
            LengthScorer(),
            ReleaseYearScorer()
        ]

    @pytest.fixture
    def tracks(
            self, tracks: list[Track], artists: list[Artist], albums: list[Album], faker: Faker
    ) -> list[Track]:
        """Fixture which returns a list of unique tracks"""
        tracks = tracks[:10]

        for track in tracks:
            track.artists = sample(artists, k=faker.random_int(1, 3))
            track.album = choice(albums)
            track.length = faker.random_int()
            track.released_at = faker.date()

        return tracks

    @pytest.fixture
    def albums(
            self, tracks: list[Track], artists: list[Artist], albums: list[Album], faker: Faker
    ) -> list[AlbumCollection]:
        """Fixture which returns a list of unique albums with tracks"""
        album_collections = []
        for album in albums:
            collection = AlbumCollection(**album.model_dump(), tracks=sample(tracks, 10))

            collection.artists = sample(artists, k=faker.random_int(1, 3))
            collection.length = faker.random_int()
            collection.released_at = faker.date()

            album_collections.append(collection)

        return album_collections

    def test_get_scorers_for_item_strings(self, model: Matcher):
        assert all(isinstance(scorer, StringScorer) for scorer in model.get_scorers_for_item("string"))

        name = HasName(name="Test Name")
        assert all(isinstance(scorer, NameScorer) for scorer in model.get_scorers_for_item(name))

        artist = HasArtists(artist="Test Artist")
        assert all(isinstance(scorer, ArtistScorer) for scorer in model.get_scorers_for_item(artist))

        album = HasAlbums(album="Test Album")
        assert all(isinstance(scorer, AlbumScorer) for scorer in model.get_scorers_for_item(album))

    def test_get_scorers_for_item_numeric(self, model: Matcher):
        assert all(isinstance(scorer, NumericScorer) for scorer in model.get_scorers_for_item(123))
        assert all(isinstance(scorer, NumericScorer) for scorer in model.get_scorers_for_item(123.45))

        assert all(isinstance(scorer, LengthScorer) for scorer in model.get_scorers_for_item(HasLength()))
        assert all(isinstance(scorer, ReleaseYearScorer) for scorer in model.get_scorers_for_item(HasReleaseDate()))

    def test_get_scorers_for_item_complex(
            self, model: Matcher, track: Track, artist: Artist, album: Album, faker: Faker
    ):
        assert model.get_scorers_for_item(track) == [
            scorer for scorer in model.scorers if scorer.__class__ in (
                NameScorer, ArtistScorer, AlbumScorer, LengthScorer, ReleaseYearScorer
            )
        ]

        assert model.get_scorers_for_item(artist) == [
            scorer for scorer in model.scorers if scorer.__class__ in (
                NameScorer, ArtistScorer
            )
        ]

        assert model.get_scorers_for_item(album) == [
            scorer for scorer in model.scorers if scorer.__class__ in (
                NameScorer, ArtistScorer, AlbumScorer, LengthScorer, ReleaseYearScorer
            )
        ]

    def test_match(self, model: Matcher, tracks: list[Track]):
        track = tracks.pop()
        assert model.match(track, [track] + tracks) is track

        model.min_score = 1  # perfect match needed
        assert model.match(track, tracks) is None

    def test_match_breaks_early(self, model: Matcher, tracks: list[Track]):
        track = tracks.pop()
        with patch.object(Matcher, "score", return_value=1) as mock_score:
            # first track is match, should break early and not check the rest
            model.match(track, [track] + tracks)
            mock_score.assert_called_once()

    def test_score_skips(self, model: Matcher, tracks: list[Track]):
        model.scorers = [scorer for scorer in model.scorers if not isinstance(scorer, NameScorer)]
        assert model.score(HasName(name="test"), tracks[0]) == 0

    def test_score(self, model: Matcher, tracks: list[Track]):
        track = tracks[0]
        assert model.score(track, track) == 1

    def test_score_always_between_0_and_1(
            self, model: Matcher, tracks: list[Track], albums: list[AlbumCollection], faker: Faker
    ):
        for scorer in model.scorers:  # ensure individual scores are inflated
            scorer.weight = faker.random_int()

        for other in tracks:
            assert 0 <= model.score(tracks[0], other) <= 1

        for other in albums:
            assert 0 <= model.score(albums[0], other) <= 1

    def test_score_respects_required_scorer(self, model: Matcher, tracks: list[Track]):
        track = tracks[0]
        other = copy(track)
        other.name = "complete-and-utter-nonsense"

        assert model.score(track, other) == 0.8  # name doesn't match but still returns score

        model.scorers.append(NameScorer(required=True))
        assert model.score(track, other) == 0  # name doesn't match and is required, so returns 0

    def test_score_items_if_configured(self, model: Matcher, albums: list[AlbumCollection]):
        album = albums.pop()

        with patch.object(Matcher, '_score_items', return_value=[0.1] * len(album.tracks)) as mock_score_items:
            model.score_items_in_collections = False
            model.score(album, album)
            mock_score_items.assert_not_called()

            model.score_items_in_collections = True
            model.score(album, album)
            mock_score_items.assert_called_once_with(album.tracks, album.tracks)

    def test_score_items(self, model: Matcher, tracks: list[Track]):
        assert model._score_items(tracks, tracks) == [1.0] * len(tracks)

        length = len(tracks) // 2
        result = model._score_items(tracks[:length], tracks[length:])
        assert len(result) == length
        assert result != [1.0] * length

    def test_score_items_breaks_early(self, model: Matcher, tracks: list[Track]):
        # breaks early every time, only checks the first track
        with patch.object(Matcher, 'score', return_value=1) as mock_score:
            model._score_items(tracks, tracks)
            assert mock_score.call_count == len(tracks)

        # never breaks early, checks every track against every other track
        length = len(tracks) // 2
        with patch.object(Matcher, 'score', return_value=0) as mock_score:
            model._score_items(tracks[:length], tracks[length:])
            assert mock_score.call_count == length ** 2
