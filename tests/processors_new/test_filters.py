from abc import ABCMeta, abstractmethod
from copy import deepcopy
from pathlib import Path
from random import shuffle, choice
from unittest import mock

import pytest
from faker import Faker

from musify.local.item.track import LocalTrack
from musify.models.properties.date import SparseDate
from musify.models.properties.file import _IsFile
from musify.models.properties.order import Position
from musify.processors_new.compare import Comparer
from musify.processors_new.filters import Filter, ValuesFilter, PathsFilter, IncludeExcludeFilter, ComparerFilter
from tests.models.testers import MusifyModelTester


class FilterTester(MusifyModelTester, metaclass=ABCMeta):
    """Base class for testing filters"""
    @abstractmethod
    def test_equality(self, model: Filter):
        raise NotImplementedError

    @abstractmethod
    def test_check(self, model: Filter, faker: Faker):
        raise NotImplementedError


class TestValuesFilter(FilterTester):

    @pytest.fixture
    def model(self, faker: Faker) -> ValuesFilter:
        values = {"".join(faker.random_letters(faker.random_int(30, 50))) for _ in range(20)}
        return ValuesFilter(values=values)

    def test_equality(self, model: ValuesFilter):
        assert model == deepcopy(model)

        new_filter = model.__class__(values=deepcopy(model.values))
        assert model == new_filter

        new_filter.values = set(deepcopy(list(model.values)[len(model.values) // 2]))
        assert model != new_filter

    def test_check(self, model: ValuesFilter, faker: Faker):
        values = list(model.values)
        assert all(model.check(value) for value in values)

        values_missing = {
            "".join(faker.random_letters(faker.random_int(30, 50))) for _ in range(10)
        } - model.values
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
        values = [choice([value, Path(value), _IsFile(path=Path(value))]) for value in expected]
        # noinspection PyTypeChecker
        assert PathsFilter(values=values).values == set(expected)


class TestIncludeExcludeFilter(FilterTester):

    @pytest.fixture
    def model(self, faker: Faker) -> IncludeExcludeFilter:
        include_values = {"".join(faker.random_letters(faker.random_int(30, 50))) for _ in range(20)}
        exclude_values = {
            "".join(faker.random_letters(faker.random_int(30, 50))) for _ in range(20)
        } - include_values

        return IncludeExcludeFilter(
            include=ValuesFilter(values=include_values),
            exclude=ValuesFilter(values=set(list(include_values)[:10] + list(exclude_values))),
        )

    def test_equality(self, model: IncludeExcludeFilter):
        new_filter = IncludeExcludeFilter(include=deepcopy(model.include), exclude=deepcopy(model.exclude))
        assert model == new_filter

        new_filter.include = deepcopy(model.exclude)
        new_filter.exclude = deepcopy(model.include)
        assert model != new_filter

    def test_check(self, model: Filter, faker: Faker):
        value = next(value for value in model.include.values if value not in model.exclude.values)
        assert model.check(value)

        value = next(value for value in model.include.values if value in model.exclude.values)
        assert not model.check(value)

        value = next(value for value in model.exclude.values)
        assert not model.check(value)

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
    def tracks(self, tracks: list[LocalTrack]) -> list[LocalTrack]:
        """
        Yields a list of :py:class:`LocalTrack` objects that match the comparers fixtures
        to be used as pytest.fixture
        """
        for track in tracks[:18]:
            track.name = "track name"

        tracks_artist = tracks[10:25]
        for track in tracks_artist:
            track.released_at = SparseDate(year=2025, month=1, day=1)

        for track in tracks:
            track.bpm = None

        return tracks

    def test_equality(self, model: ComparerFilter):
        model.match_all = choice([True, False])
        assert model == deepcopy(model)

        new_filter = ComparerFilter(comparers=deepcopy(model.comparers), match_all=model.match_all)
        assert model == new_filter

        new_filter.match_all = not model.match_all
        assert model != new_filter

    def test_check(self, model: ComparerFilter, faker: Faker):
        pass

    def test_check_with_flat_comparers_and_match_any(
            self, model: ComparerFilter, tracks: list[LocalTrack], faker: Faker
    ):
        model.comparers = list(model.comparers)  # flatten to just comparers
        model.match_all = False
        track = choice(tracks)
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
            self, model: ComparerFilter, tracks: list[LocalTrack], faker: Faker
    ):
        model.comparers = list(model.comparers)  # flatten to just comparers
        model.match_all = True
        track = choice(tracks)

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
            self, model: ComparerFilter, comparers: list[Comparer], tracks: list[LocalTrack], faker: Faker
    ):
        model.match_all = False
        track = choice(tracks)

        comparer_1_sub = mock.MagicMock()
        comparer_1_sub.check.return_value = True
        model.comparers[comparers[0]] = (True, comparer_1_sub)

        comparer_2_sub = mock.MagicMock()
        comparer_2_sub.check.return_value = False
        model.comparers[comparers[1]] = (False, comparer_2_sub)

        comparer_3_sub = mock.MagicMock()
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
