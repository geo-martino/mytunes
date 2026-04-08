from copy import deepcopy, copy
from pathlib import Path

import pytest
from faker import Faker

from musify._models.properties.date import SparseDate
from musify.local._item.track import LocalTrack
from musify.processors.compare import Comparer
from musify.processors.filters.compare import ComparerFilter
from musify.processors.filters.composite import IncludeExcludeFilter, GroupFilter
from musify.processors.filters.values import ValueFilter, PathFilter
from tests.processors.filters.testers import FilterTester


class TestIncludeExcludeFilter(FilterTester):

    @pytest.fixture
    def model(self, faker: Faker) -> IncludeExcludeFilter:
        include_values = {faker.pystr(30, 50) for _ in range(20)}
        exclude_values = {faker.pystr(30, 50) for _ in range(20)} - include_values

        return IncludeExcludeFilter(
            include=ValueFilter(values=include_values),
            exclude=ValueFilter(values=set(list(include_values)[:10] + list(exclude_values))),
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

        model.exclude = ValueFilter()
        value = next(value for value in model.include.values)
        assert model.check(value)

    def test_apply(self, model: IncludeExcludeFilter):
        expected = [value for value in model.include.values if value not in model.exclude.values]
        # there should be some overlap between include and exclude values
        assert expected != model.include.values

        assert model.apply(model.include.values) == expected
        assert not model.apply(model.exclude.values)

    def test_match(self, model: IncludeExcludeFilter):
        values = model.include.values | model.exclude.values

        result = model.match(values=values)
        assert sorted(result.included) == sorted(model.include.values)
        assert sorted(result.excluded) == sorted(model.exclude.values)


class TestGroupFilter(FilterTester):

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
    ) -> GroupFilter:
        return GroupFilter(
            include=PathFilter(values=tracks_include),
            exclude=PathFilter(values=tracks_exclude),
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
    def tracks_name(self, tracks: list[LocalTrack], faker: Faker) -> list[LocalTrack]:
        """Sample the list of tracks to test and set the same name for all these tracks"""
        tracks = faker.random_elements(tracks, 15, unique=True)
        for track in tracks:
            track.name = "track name"
        return tracks

    @pytest.fixture
    def tracks_released_at(self, tracks_name: list[LocalTrack], faker: Faker) -> list[LocalTrack]:
        """Sample the list of tracks to test and set the same released_at date for all these tracks"""
        tracks = faker.random_elements(tracks_name, 9, unique=True)
        for track in tracks:
            track.released_at = SparseDate(year=2025, month=1, day=1)
        return tracks

    @pytest.fixture
    def tracks_include(self, tracks: list[LocalTrack], tracks_name: list[LocalTrack], faker: Faker) -> list[LocalTrack]:
        """Sample the list of tracks to test and set the path to be included for all these tracks"""
        include_paths = [f"{self.library_folder}/include/{faker.file_name(extension="mp3")}" for _ in range(20)]
        tracks_unique = [track for track in tracks if track not in tracks_name]
        tracks_include = list(faker.random_elements(tracks_unique, length=7, unique=True))
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
        tracks_exclude = [
            *faker.random_elements(tracks_released_at, 3, unique=True),
            *faker.random_elements(tracks_include, 2, unique=True),
        ]
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

    def test_equality(self, model: GroupFilter, faker: Faker):
        assert model == copy(model)

        new_filter = GroupFilter(
            compare=copy(model.compare),
            include=copy(model.include),
            exclude=copy(model.exclude)
        )
        assert model == new_filter

        new_filter.include = copy(model.exclude)
        new_filter.exclude = copy(model.include)
        assert model != new_filter

    # noinspection PyMethodOverriding
    def test_check(
            self,
            model: GroupFilter,
            tracks: list[LocalTrack],
            tracks_include: list[LocalTrack],
            tracks_exclude: list[LocalTrack],
            tracks_name: list[LocalTrack],
            tracks_released_at: list[LocalTrack],
            faker: Faker,
    ):
        track = next(
            track for track in tracks
            if track in tracks_name + tracks_released_at + tracks_include and track not in tracks_exclude
        )
        assert model.check(track)
        assert not model.check(faker.random_element(tracks_exclude))

    def test_apply_empty(self, tracks_include: list[LocalTrack], tracks_exclude: list[LocalTrack]):
        matcher = GroupFilter[LocalTrack, PathFilter, PathFilter]()
        assert matcher.apply(values=tracks_include) == tracks_include
        assert matcher.apply(values=tracks_exclude) == tracks_exclude

    def test_match(
            self,
            model: GroupFilter,
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
        matcher = GroupFilter[LocalTrack, PathFilter, PathFilter](
            include=PathFilter(values=tracks_include),
            group_by="name"
        )

        result = matcher.match(values=tracks)
        assert sorted(result.included, key=self.get_path) == sorted(tracks_include, key=self.get_path)
        assert not result.excluded
        assert not result.compared
        # TODO: flakey assertion - very rare
        assert sorted(result.grouped, key=self.get_path) == sorted(tracks_name[1:], key=self.get_path)

    def test_match_with_group_by_released_at(
            self,
            tracks: list[LocalTrack],
            tracks_include: list[LocalTrack],
            tracks_released_at: list[LocalTrack],
    ):
        tracks_include = tracks_include.copy() + [tracks_released_at[0]]
        matcher = GroupFilter[LocalTrack, PathFilter, PathFilter](
            include=PathFilter(values=tracks_include),
            group_by="released_at"
        )

        result = matcher.match(values=tracks)
        assert sorted(result.included, key=self.get_path) == sorted(tracks_include, key=self.get_path)
        assert not result.excluded
        assert not result.compared
        # should ignore tracks that have no released_at value
        assert sorted(result.grouped, key=self.get_path) == sorted(tracks_released_at[1:], key=self.get_path)
