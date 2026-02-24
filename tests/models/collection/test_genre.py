from random import sample

import pytest
from faker import Faker

from musify.models.collection.genre import GenreCollection
from musify.models.item.track import Track
from musify.models.properties.uri import URI
from tests.models.testers import UniqueKeyTester


class TestGenreCollection(UniqueKeyTester):

    @pytest.fixture
    def model(self, uri: URI, faker: Faker) -> GenreCollection:
        return GenreCollection(name=faker.word(), uri=uri)

    def test_genre_name_cannot_be_empty(self, tracks: list[Track], faker: Faker):
        with pytest.raises(ValueError, match="no genres found in tracks"):
            GenreCollection()

    def test_tracks_must_be_from_same_genre_when_no_name_given(self, tracks: list[Track], faker: Faker):
        for track in tracks:
            track.genres = [faker.word() for _ in range(faker.random_int(1, 3))]
        with pytest.raises(ValueError, match="tracks are from different genres"):
            GenreCollection(tracks=tracks)

    def test_get_genre_name_from_tracks(self, tracks: list[Track]):
        name = "Test Genre"
        for track in tracks:
            track.genre = name

        genre = GenreCollection(tracks=tracks)
        assert genre.name == name

    def test_filter_tracks_on_genre_name(self, tracks: list[Track]):
        name = "Test Genre"
        expected = sample(tracks, k=len(tracks) // 2)
        for track in expected:
            track.genre = name

        genre = GenreCollection(name=name, tracks=tracks)
        assert sorted(genre.tracks) == sorted(expected)
