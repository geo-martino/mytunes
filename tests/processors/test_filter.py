from abc import ABCMeta, abstractmethod
from copy import deepcopy
from pathlib import Path
from random import sample, shuffle, randrange, choice

import pytest

from musify.field import TagFields
from musify.file.path_mapper import PathStemMapper, PathMapper
from musify.libraries.local.track import LocalTrack
from musify.libraries.local.track.field import LocalTrackField
from musify.processors.base import Filter
from musify.processors.compare import Comparer
from musify.processors.filter import FilterDefinedList, FilterComparers, FilterIncludeExclude
from musify.processors.filter_matcher import FilterMatcher
from tests.libraries.local.track.utils import random_tracks
from tests.libraries.local.utils import path_track_all
from tests.testers import PrettyPrinterTester
from tests.utils import random_str, path_resources


def get_path(track: LocalTrack) -> Path:
    """The key to sort on when making assertions in tests"""
    return track.path


class FilterTester(PrettyPrinterTester, metaclass=ABCMeta):
    @abstractmethod
    def test_equality(self, obj: Filter):
        raise NotImplementedError


class TestFilterDefinedList(FilterTester):

    @pytest.fixture
    def obj(self) -> FilterDefinedList:
        return FilterDefinedList(values=[random_str(30, 50) for _ in range(20)])

    def test_equality(self, obj: FilterDefinedList):
        assert obj == deepcopy(obj)

        new_filter = FilterDefinedList(values=deepcopy(obj.values))
        assert obj == new_filter

        new_filter.values = deepcopy(list(obj.values)[len(obj.values) // 2])
        assert obj != new_filter

    def test_filter(self):
        values = [random_str(30, 50) for _ in range(20)]

        assert FilterDefinedList().process(values) == values

        expected = values
        expected_shuffled = expected.copy()
        shuffle(expected_shuffled)
        filter_ = FilterDefinedList(values=values)
        assert filter_(values[:10]) == values[:10]


class TestFilterComparers(FilterTester):

    @pytest.fixture(scope="class")
    def comparers(self) -> list[Comparer]:
        """Yields a list of :py:class:`Comparer` objects to be used as pytest.fixture."""
        return [
            Comparer(condition="is", expected="album name", field=LocalTrackField.ALBUM),
            Comparer(condition="starts with", expected="artist", field=LocalTrackField.ARTIST)
        ]

    @pytest.fixture
    def obj(self, comparers: list[Comparer]) -> FilterComparers:
        return FilterComparers(comparers=comparers)

    @pytest.fixture
    def tracks(self) -> list[LocalTrack]:
        """
        Yields a list of :py:class:`LocalTrack` objects that match the comparers fixtures
        to be used as pytest.fixture
        """
        tracks = random_tracks(30)
        for track in tracks[:18]:
            track.album = "album name"

        tracks_artist = tracks[10:25]
        for track in tracks_artist:
            track.artist = "artist name"

        return tracks

    def test_equality(self, obj: FilterComparers):
        obj.match_all = choice([True, False])
        assert obj == deepcopy(obj)

        new_filter = FilterComparers(comparers=deepcopy(obj.comparers), match_all=obj.match_all)
        assert obj == new_filter

        new_filter.match_all = not obj.match_all
        assert obj != new_filter

    def test_filter(self, comparers: list[Comparer], tracks: list[LocalTrack]):
        assert FilterComparers().process(tracks) == tracks

        comparer = FilterComparers(comparers=comparers, match_all=False)
        assert comparer(tracks) == tracks[:25]

        comparer = FilterComparers(comparers=comparers, match_all=True)
        assert comparer(tracks) == tracks[10:18]

    def test_filter_nested(self, comparers: list[Comparer], tracks: list[LocalTrack]):
        sub_filter_1 = FilterComparers(
            comparers=[
                Comparer(condition="is", expected=2020, field=LocalTrackField.YEAR),
                Comparer(condition="in range", expected=[80, 100], field=LocalTrackField.BPM)
            ],
            match_all=False
        )
        sub_filter_2 = FilterComparers(
            comparers=Comparer(condition="greater than", expected=20, field=LocalTrackField.TRACK_NUMBER),
            match_all=True
        )

        for i, track in enumerate(tracks):
            track.track_number = i + 1
            track.year = 2020 if i >= 8 else 1990
            track.bpm = randrange(85, 95) if 10 < i < 15 else 120

        comparer = FilterComparers(
            comparers={comparers[0]: (False, sub_filter_1), comparers[1]: (False, sub_filter_2)},
            match_all=False
        )
        assert sorted(comparer(tracks), key=lambda x: x.track_number) == tracks  # loose conditions, matches everything

        comparer = FilterComparers(
            comparers={comparers[0]: (True, sub_filter_1), comparers[1]: (False, sub_filter_2)},
            match_all=False
        )
        assert sorted(comparer(tracks), key=lambda x: x.track_number) == tracks[8:]

        sub_filter_1.match_all = True
        comparer = FilterComparers(
            comparers={comparers[0]: (True, sub_filter_1), comparers[1]: (False, sub_filter_2)},
            match_all=False
        )
        assert sorted(comparer(tracks), key=lambda x: x.track_number) == tracks[10:]

        comparer = FilterComparers(
            comparers={comparers[0]: (True, sub_filter_1), comparers[1]: (True, sub_filter_2)},
            match_all=False
        )
        assert sorted(comparer(tracks), key=lambda x: x.track_number) == tracks[11:15] + tracks[20:25]

        comparer = FilterComparers(
            comparers={comparers[0]: (True, sub_filter_1), comparers[1]: (True, sub_filter_2)},
            match_all=True
        )
        assert not comparer(tracks)  # no overlap between the 2 parent comparers


class TestFilterIncludeExclude(FilterTester):

    @pytest.fixture
    def obj(self) -> FilterIncludeExclude:
        include_values = [random_str(30, 50) for _ in range(20)]
        return FilterIncludeExclude(
            include=FilterDefinedList(include_values),
            exclude=FilterDefinedList(include_values[:10] + [random_str(30, 50) for _ in range(20)]),
        )

    def test_equality(self, obj: FilterIncludeExclude):
        assert obj == deepcopy(obj)

        new_filter = FilterIncludeExclude(include=deepcopy(obj.include), exclude=deepcopy(obj.exclude))
        assert obj == new_filter

        new_filter.include = deepcopy(obj.exclude)
        new_filter.exclude = deepcopy(obj.include)
        assert obj != new_filter

    def test_filter(self, obj: FilterIncludeExclude):
        assert obj(obj.include.values) == obj.include.values[10:20]
        assert not obj(obj.exclude.values)


class TestFilterMatcher(FilterTester):

    library_folder = "/path/to/library"

    @pytest.fixture(scope="class")
    def comparers(self) -> list[Comparer]:
        """Yields a list :py:class:`Comparer` objects to be used as pytest.fixture."""
        return [
            Comparer(condition="is", expected="album name", field=LocalTrackField.ALBUM),
            Comparer(condition="starts with", expected="artist", field=LocalTrackField.ARTIST)
        ]

    @pytest.fixture
    def obj(self, comparers: list[Comparer]) -> FilterMatcher:
        return FilterMatcher(
            comparers=FilterComparers(comparers),
            include=FilterDefinedList(
                [f"{self.library_folder}/include/{random_str(30, 50)}.MP3" for _ in range(20)],
            ),
            exclude=FilterDefinedList(
                [f"{self.library_folder}/exclude/{random_str(30, 50)}.MP3" for _ in range(20)],
            ),
        )

    @pytest.fixture(scope="class")
    def tracks(self) -> list[LocalTrack]:
        """Yield a list of random LocalTracks to use for testing the :py:class:`LocalMatcher`"""
        tracks = random_tracks(30)
        return tracks

    @pytest.fixture(scope="class")
    def tracks_album(self, tracks: list[LocalTrack]) -> list[LocalTrack]:
        """Sample the list of tracks to test and set the same album name for all these tracks"""
        tracks_album = sample(tracks, 15)
        for track in tracks_album:
            track.album = "album name"
        return tracks_album

    @pytest.fixture(scope="class")
    def tracks_artist(self, tracks_album: list[LocalTrack]) -> list[LocalTrack]:
        """Sample the list of tracks to test and set the same artist name for all these tracks"""
        tracks_artist = sample(tracks_album, 9)
        for track in tracks_artist:
            track.artist = "artist name"
        return tracks_artist

    @pytest.fixture(scope="class")
    def tracks_include(self, tracks: list[LocalTrack], tracks_album: list[LocalTrack]) -> list[LocalTrack]:
        """Sample the list of tracks to test and set the path to be included for all these tracks"""
        include_paths = [f"{self.library_folder}/include/{random_str(30, 50)}.MP3" for _ in range(20)]
        tracks_include = sample([track for track in tracks if track not in tracks_album], 7)

        for i, track in enumerate(tracks_include):
            track._path = Path(include_paths[i])
        return tracks_include

    @pytest.fixture(scope="class")
    def tracks_exclude(self, tracks_artist: list[LocalTrack], tracks_include: list[LocalTrack]) -> list[LocalTrack]:
        """Sample the list of tracks to test and set the path to be excluded for all these tracks"""
        exclude_paths = [f"{self.library_folder}/exclude/{random_str(30, 50)}.MP3" for _ in range(20)]
        tracks_exclude = sample(tracks_artist, 3) + sample(tracks_include, 2)

        for i, track in enumerate(tracks_exclude):
            track._path = Path(exclude_paths[i])
        return tracks_exclude

    @pytest.fixture(scope="class")
    def path_mapper(self) -> PathStemMapper:
        """Yields a :py:class:`PathMapper` that can map paths from the test playlist files"""
        yield PathStemMapper(stem_map={"../": path_resources}, available_paths=path_track_all)

    def test_equality(self, obj: FilterMatcher):
        assert obj == deepcopy(obj)

        new_filter = FilterMatcher(
            comparers=deepcopy(obj.comparers),
            include=deepcopy(obj.include),
            exclude=deepcopy(obj.exclude)
        )
        assert obj == new_filter

        new_filter.include = deepcopy(obj.exclude)
        new_filter.exclude = deepcopy(obj.include)
        assert obj != new_filter

    def test_filter_empty(self, tracks_include: list[LocalTrack], tracks_exclude: list[LocalTrack]):
        assert FilterMatcher().process(values=tracks_include) == tracks_include
        assert FilterMatcher().process(values=tracks_exclude) == tracks_exclude

    def test_filter_no_comparers(
            self,
            tracks: list[LocalTrack],
            tracks_include: list[LocalTrack],
            tracks_exclude: list[LocalTrack],
            path_mapper: PathMapper
    ):
        matcher = FilterMatcher(
            include=FilterDefinedList(list(map(get_path, tracks_include))),
            exclude=FilterDefinedList(list(map(get_path, tracks_exclude))),
        )
        matcher.include.transform = lambda x: Path(path_mapper.map(x, check_existence=False))
        matcher.exclude.transform = lambda x: Path(path_mapper.map(x, check_existence=False))
        tracks_include_reduced = [track for track in tracks_include if track not in tracks_exclude]

        assert matcher(values=tracks) == tracks_include_reduced
        assert matcher.process(values=tracks) == tracks_include_reduced

    def test_filter_on_any_comparers(
            self,
            comparers: list[Comparer],
            tracks: list[LocalTrack],
            tracks_album: list[LocalTrack],
            tracks_include: list[LocalTrack],
            tracks_exclude: list[LocalTrack],
            path_mapper: PathMapper,
    ):
        matcher = FilterMatcher(
            comparers=FilterComparers(comparers, match_all=False),
            include=FilterDefinedList(list(map(get_path, tracks_include))),
            exclude=FilterDefinedList(list(map(get_path, tracks_exclude))),
        )
        matcher.include.transform = lambda x: Path(path_mapper.map(x, check_existence=False))
        matcher.exclude.transform = lambda x: Path(path_mapper.map(x, check_existence=False))
        tracks_album_reduced = [track for track in tracks_album if track not in tracks_exclude]
        tracks_include_reduced = [track for track in tracks_include if track not in tracks_exclude]

        matches = sorted(matcher(values=tracks), key=get_path)
        assert matches == sorted(tracks_album_reduced + tracks_include_reduced, key=get_path)

    def test_filter_on_all_comparers(
            self,
            comparers: list[Comparer],
            tracks: list[LocalTrack],
            tracks_album: list[LocalTrack],
            tracks_artist: list[LocalTrack],
            tracks_include: list[LocalTrack],
            tracks_exclude: list[LocalTrack],
            path_mapper: PathMapper,
    ):
        matcher = FilterMatcher(
            comparers=FilterComparers(comparers, match_all=True),
            include=FilterDefinedList(list(map(get_path, tracks_include))),
            exclude=FilterDefinedList(list(map(get_path, tracks_exclude))),
        )
        matcher.include.transform = lambda x: Path(path_mapper.map(x, check_existence=False))
        matcher.exclude.transform = lambda x: Path(path_mapper.map(x, check_existence=False))

        tracks_artist_reduced = [track for track in tracks_artist if track not in tracks_exclude]
        tracks_include_reduced = [track for track in tracks_include if track not in tracks_exclude]

        matches = sorted(matcher(values=tracks), key=get_path)
        assert matches == sorted(tracks_artist_reduced + tracks_include_reduced, key=get_path)

    def test_extend_result_on_group_by_album(
            self,
            tracks: list[LocalTrack],
            tracks_include: list[LocalTrack],
            tracks_album: list[LocalTrack],
            path_mapper: PathMapper
    ):
        tracks_include = tracks_include.copy() + [tracks_album[0]]
        matcher = FilterMatcher(
            include=FilterDefinedList(list(map(get_path, tracks_include))),
            group_by=TagFields.ALBUM
        )
        matcher.include.transform = lambda x: Path(path_mapper.map(x, check_existence=False))

        result = matcher.process_to_result(values=tracks)
        assert sorted(result.included, key=get_path) == sorted(tracks_include, key=get_path)
        assert not result.excluded
        assert not result.compared
        assert result.grouped
        assert sorted(result.grouped, key=get_path) == sorted(tracks_album[1:], key=get_path)

        combined_expected = sorted(tracks_include + tracks_album[1:], key=get_path)
        assert sorted(result.combined, key=get_path) == combined_expected

    def test_extend_result_on_group_by_artist(
            self,
            tracks: list[LocalTrack],
            tracks_include: list[LocalTrack],
            tracks_artist: list[LocalTrack],
            path_mapper: PathMapper
    ):
        tracks_include = tracks_include.copy() + [tracks_artist[0]]
        matcher = FilterMatcher(
            include=FilterDefinedList(list(map(get_path, tracks_include))),
            group_by=TagFields.ARTIST
        )
        matcher.include.transform = lambda x: Path(path_mapper.map(x, check_existence=False))
        result = matcher.process_to_result(values=tracks)
        assert sorted(result.included, key=get_path) == sorted(tracks_include, key=get_path)
        assert not result.excluded
        assert not result.compared
        assert result.grouped
        assert sorted(result.grouped, key=get_path) == sorted(tracks_artist[1:], key=get_path)

        combined_expected = sorted(tracks_include + tracks_artist[1:], key=get_path)
        assert sorted(result.combined, key=get_path) == combined_expected
