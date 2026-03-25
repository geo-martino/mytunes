from abc import ABCMeta, abstractmethod
from copy import deepcopy
from pathlib import Path
from random import shuffle, choice, sample
from unittest.mock import MagicMock

import pytest
from faker import Faker

from musify.local.item.track import LocalTrack
from musify.models.properties.date import SparseDate
from musify.models.properties.file import IsLocalFile
from musify.processors_new.compare import Comparer
from musify.processors_new.filters import Filter, ValuesFilter, PathsFilter, IncludeExcludeFilter, ComparerFilter, \
    MatchFilter
from tests.models.testers import BaseModelTester


class FilterTester(BaseModelTester, metaclass=ABCMeta):
    """Base class for testing filters"""
    @abstractmethod
    def test_equality(self, model: Filter, faker: Faker):
        raise NotImplementedError

    @abstractmethod
    def test_check(self, model: Filter, faker: Faker):
        raise NotImplementedError


class TestValuesFilter(FilterTester):

    @pytest.fixture
    def model(self, faker: Faker) -> ValuesFilter:
        values = {faker.pystr(30, 50) for _ in range(20)}
        return ValuesFilter(values=values)

    def test_equality(self, model: ValuesFilter, faker: Faker):
        assert model == deepcopy(model)

        new_filter = model.__class__(values=deepcopy(model.values))
        assert model == new_filter

        new_filter.values = set(deepcopy(list(model.values)[len(model.values) // 2]))
        assert model != new_filter

    def test_check(self, model: ValuesFilter, faker: Faker):
        values = list(model.values)
        assert all(model.check(value) for value in values)

        values_missing = {faker.pystr(30, 50) for _ in range(10)} - model.values
        assert not any(model.check(value) for value in values_missing)

    def test_apply_on_empty_filter(self, model: ValuesFilter):
        assert model.__class__().apply(model.values) == list(model.values)

    def test_apply(self, model: ValuesFilter):
        values = list(model.values)
        expected = values.copy()
        shuffle(expected)

        filter_ = ValuesFilter(values=model.values)
        assert filter_.apply(values[:10]) == values[:10]


class TestPathsFilter(TestValuesFilter):

    @pytest.fixture
    def model(self, faker: Faker) -> PathsFilter:
        values = {faker.file_path() for _ in range(20)}
        return PathsFilter(values=values)

    def test_extract_values(self, model: PathsFilter, faker: Faker):
        expected = [faker.file_path() for _ in range(10)]
        values = [choice([value, Path(value), IsLocalFile(path=Path(value))]) for value in expected]
        # noinspection PyTypeChecker
        assert PathsFilter(values=values).values == set(expected)


class TestIncludeExcludeFilter(FilterTester):

    @pytest.fixture
    def model(self, faker: Faker) -> IncludeExcludeFilter:
        include_values = {faker.pystr(30, 50) for _ in range(20)}
        exclude_values = {faker.pystr(30, 50) for _ in range(20)} - include_values

        return IncludeExcludeFilter(
            include=ValuesFilter(values=include_values),
            exclude=ValuesFilter(values=set(list(include_values)[:10] + list(exclude_values))),
        )

    def test_equality(self, model: IncludeExcludeFilter, faker: Faker):
        new_filter = IncludeExcludeFilter(include=deepcopy(model.include), exclude=deepcopy(model.exclude))
        assert model == new_filter

        new_filter.include = deepcopy(model.exclude)
        new_filter.exclude = deepcopy(model.include)
        assert model != new_filter

    def test_check(self, model: IncludeExcludeFilter, faker: Faker):
        value = next(value for value in model.include.values if value not in model.exclude.values)
        assert model.check(value)

        value = next(value for value in model.include.values if value in model.exclude.values)
        assert not model.check(value)

        value = next(value for value in model.exclude.values)
        assert not model.check(value)

        model.exclude = ValuesFilter()
        value = next(value for value in model.include.values)
        assert model.check(value)

    def test_apply(self, model: IncludeExcludeFilter):
        expected = [value for value in model.include.values if value not in model.exclude.values]
        # there should be some overlap between include and exclude values
        assert expected != model.include.values

        assert model.apply(model.include.values) == expected
        assert not model.apply(model.exclude.values)


class TestComparerFilter(FilterTester):

    @pytest.fixture(scope="class")
    def comparers(self) -> list[Comparer]:
        """Yields a list of :py:class:`Comparer` objects to be used as pytest.fixture."""
        return [
            Comparer(condition="starts with", expected="track", field="name"),
            Comparer(condition="is", expected="2025-01-01", field="released_at"),
            Comparer(condition="is_null", field="bpm"),
        ]

    @pytest.fixture
    def model(self, comparers: list[Comparer]) -> ComparerFilter:
        return ComparerFilter(comparers=comparers)

    @pytest.fixture
    def tracks(self, local_tracks: list[LocalTrack]) -> list[LocalTrack]:
        """
        Yields a list of :py:class:`LocalTrack` objects that match the comparers fixtures
        to be used as pytest.fixture
        """
        for track in local_tracks[:18]:
            track.name = "track name"

        tracks_released_at = local_tracks[10:25]
        for track in tracks_released_at:
            track.released_at = SparseDate(year=2025, month=1, day=1)

        for track in local_tracks:
            track.bpm = None

        return local_tracks

    def test_equality(self, model: ComparerFilter, faker: Faker):
        model.match_all = faker.boolean()
        assert model == deepcopy(model)

        new_filter = ComparerFilter(comparers=deepcopy(model.comparers), match_all=model.match_all)
        assert model == new_filter

        new_filter.match_all = not model.match_all
        assert model != new_filter

    def test_check(self, model: ComparerFilter, faker: Faker):
        pass

    def test_check_with_flat_comparers_and_match_any(
            self, model: ComparerFilter, track: LocalTrack, faker: Faker
    ):
        model.comparers = list(model.comparers)  # flatten to just comparers
        model.match_all = False
        track.bpm = 123.45

        track.name = "track name"
        track.released_at = SparseDate(year=2020, month=1, day=1)
        assert model.check(track)

        track.name = "new_name"
        track.released_at = SparseDate(year=2025, month=1, day=1)
        assert model.check(track)

        track.name = "new_name"
        track.released_at = SparseDate(year=2020, month=1, day=1)
        assert not model.check(track)

    def test_check_with_flat_comparers_and_match_all(
            self, model: ComparerFilter, track: LocalTrack, faker: Faker
    ):
        model.comparers = list(model.comparers)  # flatten to just comparers
        model.match_all = True

        track.name = "track name"
        track.released_at = SparseDate(year=2025, month=1, day=1)
        assert model.check(track)

        track.name = "new_name"
        track.released_at = SparseDate(year=2025, month=1, day=1)
        assert not model.check(track)

        track.name = "new_name"
        track.released_at = SparseDate(year=2020, month=1, day=1)
        assert not model.check(track)

    def test_check_with_nested_comparers_and_match_any(
            self, model: ComparerFilter, comparers: list[Comparer], track: LocalTrack, faker: Faker
    ):
        model.match_all = False

        comparer_1_sub = MagicMock()
        comparer_1_sub.check.return_value = True
        model.comparers[comparers[0]] = (True, comparer_1_sub)

        comparer_2_sub = MagicMock()
        comparer_2_sub.check.return_value = False
        model.comparers[comparers[1]] = (False, comparer_2_sub)

        comparer_3_sub = MagicMock()
        comparer_3_sub.check.return_value = False
        model.comparers[comparers[2]] = (True, comparer_3_sub)

        track.name = "track name"
        track.released_at = SparseDate(year=2025, month=1, day=1)
        track.bpm = 123.45
        assert model.check(track)

        track.name = "new_name"
        track.released_at = SparseDate(year=2025, month=1, day=1)
        track.bpm = 123.45
        assert model.check(track)

        track.name = "new_name"
        track.released_at = SparseDate(year=2020, month=1, day=1)
        track.bpm = 123.45
        assert not model.check(track)

        track.name = "new_name"
        track.released_at = SparseDate(year=2020, month=1, day=1)
        track.bpm = 123.45
        assert not model.check(track)

    def test_apply(self, comparers: list[Comparer], tracks: list[LocalTrack]):
        assert ComparerFilter().apply(tracks) == tracks

        comparers = comparers[:2]  # exclude 'bpm is null' comparer
        filter_ = ComparerFilter(comparers=comparers, match_all=False)
        assert filter_.apply(tracks) == tracks[:25]

        filter_ = ComparerFilter(comparers=comparers, match_all=True)
        assert filter_.apply(tracks) == tracks[10:18]


class TestMatcherFilter(FilterTester):

    library_folder = "/path/to/library"

    @pytest.fixture(scope="class")
    def comparers(self) -> list[Comparer]:
        """Yields a list of :py:class:`Comparer` objects to be used as pytest.fixture."""
        return [
            Comparer(condition="starts with", expected="track", field="name"),
            Comparer(condition="is", expected="2025-01-01", field="released_at"),
        ]

    @pytest.fixture
    def model(
            self,
            tracks_include: list[LocalTrack],
            tracks_exclude: list[LocalTrack],
            comparers: list[Comparer],
            faker: Faker
    ) -> MatchFilter:
        return MatchFilter(
            include=PathsFilter(values=tracks_include),
            exclude=PathsFilter(values=tracks_exclude),
            compare=ComparerFilter(comparers=comparers, match_all=False),
        )

    @pytest.fixture
    def tracks(self, local_tracks: list[LocalTrack]) -> list[LocalTrack]:
        """
        Yields a list of :py:class:`LocalTrack` objects that match the comparers fixtures
        to be used as pytest.fixture
        """
        return local_tracks

    @pytest.fixture
    def tracks_name(self, tracks: list[LocalTrack]) -> list[LocalTrack]:
        """Sample the list of tracks to test and set the same name for all these tracks"""
        tracks = sample(tracks, 15)
        for track in tracks:
            track.name = "track name"
        return tracks

    @pytest.fixture
    def tracks_released_at(self, tracks_name: list[LocalTrack]) -> list[LocalTrack]:
        """Sample the list of tracks to test and set the same released_at date for all these tracks"""
        tracks = sample(tracks_name, 9)
        for track in tracks:
            track.released_at = SparseDate(year=2025, month=1, day=1)
        return tracks

    @pytest.fixture
    def tracks_include(self, tracks: list[LocalTrack], tracks_name: list[LocalTrack], faker: Faker) -> list[LocalTrack]:
        """Sample the list of tracks to test and set the path to be included for all these tracks"""
        include_paths = [f"{self.library_folder}/include/{faker.file_name(extension="mp3")}" for _ in range(20)]
        tracks_include = sample([track for track in tracks if track not in tracks_name], 7)
        tracks_include.sort(key=lambda tr: tracks.index(tr))

        for i, track in enumerate(tracks_include):
            track._path = Path(include_paths[i])
        return tracks_include

    @pytest.fixture
    def tracks_exclude(
            self, tracks_released_at: list[LocalTrack], tracks_include: list[LocalTrack], faker: Faker
    ) -> list[LocalTrack]:
        """Sample the list of tracks to test and set the path to be excluded for all these tracks"""
        exclude_paths = [f"{self.library_folder}/exclude/{faker.file_name(extension="mp3")}" for _ in range(20)]
        tracks_exclude = sample(tracks_released_at, 3) + sample(tracks_include, 2)
        tracks_exclude.sort(
            key=lambda tr: tracks_released_at.index(tr) if tr in tracks_released_at else tracks_include.index(tr)
        )

        for i, track in enumerate(tracks_exclude):
            track._path = Path(exclude_paths[i])
        return tracks_exclude

    @staticmethod
    def get_path(track: LocalTrack) -> Path:
        """The key to sort on when making assertions in tests"""
        return track.path

    def test_equality(self, model: MatchFilter, faker: Faker):
        assert model == deepcopy(model)

        new_filter = MatchFilter(
            compare=deepcopy(model.compare),
            include=deepcopy(model.include),
            exclude=deepcopy(model.exclude)
        )
        assert model == new_filter

        new_filter.include = deepcopy(model.exclude)
        new_filter.exclude = deepcopy(model.include)
        assert model != new_filter

    # noinspection PyMethodOverriding
    def test_check(
            self,
            model: MatchFilter,
            faker: Faker,
            tracks: list[LocalTrack],
            tracks_include: list[LocalTrack],
            tracks_exclude: list[LocalTrack],
            tracks_name: list[LocalTrack],
            tracks_released_at: list[LocalTrack],
    ):
        track = next(
            track for track in tracks
            if track in tracks_name + tracks_released_at + tracks_include and track not in tracks_exclude
        )
        assert model.check(track)
        assert not model.check(choice(tracks_exclude))

    def test_apply_empty(self, tracks_include: list[LocalTrack], tracks_exclude: list[LocalTrack]):
        assert MatchFilter().apply(values=tracks_include) == tracks_include
        assert MatchFilter().apply(values=tracks_exclude) == tracks_exclude

    def test_match(
            self,
            model: MatchFilter,
            tracks: list[LocalTrack],
            tracks_name: list[LocalTrack],
            tracks_released_at: list[LocalTrack],
            tracks_include: list[LocalTrack],
            tracks_exclude: list[LocalTrack],
    ):
        result = model.match(values=tracks)
        assert sorted(result.included, key=self.get_path) == sorted(tracks_include, key=self.get_path)
        assert sorted(result.excluded, key=self.get_path) == sorted(tracks_exclude, key=self.get_path)
        compared_expected = tracks_name + [tr for tr in tracks_released_at if tr not in tracks_name]
        assert sorted(result.compared, key=self.get_path) == sorted(compared_expected, key=self.get_path)
        assert not result.grouped

    def test_match_with_group_by_name(
            self,
            tracks: list[LocalTrack],
            tracks_include: list[LocalTrack],
            tracks_name: list[LocalTrack],
    ):
        tracks_include = tracks_include.copy() + [tracks_name[0]]
        matcher = MatchFilter(
            include=PathsFilter(values=tracks_include),
            group_by="name"
        )

        result = matcher.match(values=tracks)
        assert sorted(result.included, key=self.get_path) == sorted(tracks_include, key=self.get_path)
        assert not result.excluded
        assert not result.compared
        assert sorted(result.grouped, key=self.get_path) == sorted(tracks_name[1:], key=self.get_path)

    def test_match_with_group_by_released_at(
            self,
            tracks: list[LocalTrack],
            tracks_include: list[LocalTrack],
            tracks_released_at: list[LocalTrack],
    ):
        tracks_include = tracks_include.copy() + [tracks_released_at[0]]
        matcher = MatchFilter(
            include=PathsFilter(values=tracks_include),
            group_by="released_at"
        )

        result = matcher.match(values=tracks)
        assert sorted(result.included, key=self.get_path) == sorted(tracks_include, key=self.get_path)
        assert not result.excluded
        assert not result.compared
        # should ignore tracks that have no released_at value
        assert sorted(result.grouped, key=self.get_path) == sorted(tracks_released_at[1:], key=self.get_path)
