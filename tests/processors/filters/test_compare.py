from copy import copy
from unittest.mock import MagicMock

import pytest
from faker import Faker
from mytunes._models.properties.date import SparseDate
from mytunes.local._item.track import LocalTrack
from mytunes.processors.compare import Comparer
from mytunes.processors.filters.compare import ComparerFilter
from tests.processors.filters.testers import FilterTester


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

    def test_from_comparer(self, comparers: list[ComparerFilter]):
        data = comparers[0].model_dump()
        assert ComparerFilter.model_validate(data).comparers.keys() == {comparers[0]}

    def test_from_comparers(self, comparers: list[ComparerFilter]):
        data = [cmp.model_dump() for cmp in comparers]
        assert ComparerFilter.model_validate(data).comparers.keys() == set(comparers)

    def test_equality(self, model: ComparerFilter, faker: Faker):
        model.match_all = faker.boolean()
        assert model == copy(model)

        new_filter = ComparerFilter(comparers=copy(model.comparers), match_all=model.match_all)
        assert model == new_filter

        new_filter.match_all = not model.match_all
        assert model != new_filter

    def test_check(self, model: ComparerFilter, faker: Faker):
        pass  # deferred to more specific tests below

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
        comparer_1_sub.combine_all = True
        comparer_1_sub.check.return_value = True
        model.comparers[comparers[0]] = comparer_1_sub

        comparer_2_sub = MagicMock()
        comparer_2_sub.combine_all = False
        comparer_2_sub.check.return_value = False
        model.comparers[comparers[1]] = comparer_2_sub

        comparer_3_sub = MagicMock()
        comparer_3_sub.combine_all = True
        comparer_3_sub.check.return_value = False
        model.comparers[comparers[2]] = comparer_3_sub

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
