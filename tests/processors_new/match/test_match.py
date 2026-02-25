import pytest
from faker import Faker

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
from tests.models.testers import MusifyModelTester


class TestMatcher(MusifyModelTester):
    @pytest.fixture
    def model(self, scorers: list[Scorer]) -> Matcher:
        return Matcher(scorers=scorers)

    @pytest.fixture
    def scorers(self) -> list[Scorer]:
        """Fixture for providing a list of scorers to test the Matcher model with."""
        return [
            NameScorer(), ArtistScorer(), AlbumScorer(), LengthScorer(), ReleaseYearScorer()
        ]

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
            NameScorer(), ArtistScorer(), AlbumScorer(), LengthScorer(), ReleaseYearScorer()
        ]
        assert model.get_scorers_for_item(artist) == [
            NameScorer(), ArtistScorer()
        ]
        assert model.get_scorers_for_item(album) == [
            NameScorer(), ArtistScorer(), AlbumScorer(), LengthScorer(), ReleaseYearScorer()
        ]

