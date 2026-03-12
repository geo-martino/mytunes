from random import sample
from typing import Any

import pytest
from faker import Faker

from musify.models.collection import PageCursor
from musify.models.collection.genre import GenreCollection, RemoteGenreCollection
from musify.models.item.track import Track
from tests.models.collection.testers import RemoteCollectionTester
from tests.models.testers import UniqueKeyTester
from tests.utils import SimpleURI


class TestGenreCollection(UniqueKeyTester):

    @pytest.fixture
    def model(self, faker: Faker) -> GenreCollection:
        return GenreCollection(name=faker.word())

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

    def test_items_count(self, tracks: list[Track]):
        name = "Test Genre"
        for track in tracks:
            track.genre = name

        model = GenreCollection(name=name, tracks=tracks)
        assert model.count == len(tracks)


class TestRemoteGenreCollection(RemoteCollectionTester):
    @pytest.fixture
    def model(self, cursor: PageCursor, faker: Faker) -> RemoteGenreCollection:
        uri = SimpleURI.from_id(
            faker.random_int(int(10e9), int(10e10)), kind=RemoteGenreCollection.type
        )
        return RemoteGenreCollection[SimpleURI, Any, PageCursor](
            name=faker.word(),
            uri=uri,
            total=faker.random_int(1, 20),
            cursor=cursor
        )
