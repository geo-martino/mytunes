from unittest.mock import patch

import pytest
from faker import Faker
from mytunes._models import AttributeModel
from mytunes._models.item.track import Track
from mytunes.exception import MyTunesValueError
from mytunes.processors.sort import ItemSorter
from mytunes.processors.tagger._setter import ValueSetter, GroupedSetter, SortedSetter, IncrementalSetter
from mytunes.processors.tagger.values import FixedValue, MinValue
from tests.testers import BaseModelTester


class TestValueSetter(BaseModelTester):
    @pytest.fixture
    def model(self, faker: Faker) -> ValueSetter:
        return ValueSetter(field="artist", value=FixedValue(name="name", value=faker.name()))

    def test_set_value(self, model: ValueSetter, track: Track, faker: Faker):
        fixed_value = FixedValue(name="name", value=faker.name())
        model = ValueSetter(field="artist", value=fixed_value)

        assert track.artist != fixed_value.value
        model.set(track)
        assert track.artist == fixed_value.value


class GroupedSetterTester(BaseModelTester):
    def test_validates_item_in_group(self, model: GroupedSetter, tracks: list[Track], faker: Faker):
        track = faker.random_element(tracks)
        with patch.object(AttributeModel, "__setattr__"):
            model.set(track, tracks)  # should pass

        track = tracks.pop(0)
        with pytest.raises(MyTunesValueError):
            model.set(track, tracks)

    def test_set_value_with_group(
            self, model: GroupedSetter, tracks: list[Track], tracks_group: list[Track], faker: Faker
    ):
        track = faker.random_element(tracks_group)
        expected = min(track.track.number for track in tracks_group)

        model.group_by = ["name"]
        model.set(track, tracks)
        assert track.track.number == expected


class TestGroupedSetter(GroupedSetterTester):
    @pytest.fixture
    def model(self, faker: Faker) -> GroupedSetter:
        return GroupedSetter(field="track", value=MinValue(field="track"))

    def test_set_value(self, model: GroupedSetter, tracks: list[Track], faker: Faker):
        track = faker.random_element(tracks)
        expected = min(track.track.number for track in tracks)

        model.set(track, tracks)
        assert track.track.number == expected


class TestSortedSetter(GroupedSetterTester):
    @pytest.fixture
    def model(self, faker: Faker) -> SortedSetter:
        return SortedSetter(field="track.number", value=MinValue(field="track.number"))

    def test_set_value(self, model: SortedSetter, tracks: list[Track], faker: Faker):
        track = faker.random_element(tracks)
        expected = min(track.track.number for track in tracks)

        model.set(track, tracks)
        assert track.track.number == expected

    def test_set_value_with_sort(self, model: SortedSetter, tracks: list[Track], faker: Faker):
        track = faker.random_element(tracks)
        expected = min([track.track.number for track in tracks])

        model.sort_by = ItemSorter(sort_fields={"name": True})
        model.set(track, tracks)
        assert track.track.number == expected


class TestIncrementalSetter(GroupedSetterTester):
    @pytest.fixture
    def model(self, faker: Faker) -> IncrementalSetter:
        start = faker.random_int(1, 10)
        increment = faker.random_int(1, 10)
        return IncrementalSetter(field="track.number", start=start, increment=increment)

    def test_set_value(self, model: IncrementalSetter, tracks: list[Track], faker: Faker):
        track = faker.random_element(tracks)
        track.track.total = None  # avoid errors with Position validation
        expected = model.start + tracks.index(track) * model.increment

        model.set(track, tracks)
        assert track.track.number == expected

    def test_set_value_with_sort(self, model: IncrementalSetter, tracks: list[Track], faker: Faker):
        track = faker.random_element(tracks)
        track.track.total = None  # avoid errors with Position validation
        expected = model.start + sorted(tracks, key=lambda x: x.name, reverse=True).index(track) * model.increment

        model.sort_by = ItemSorter(sort_fields={"name": True})
        model.set(track, tracks)
        assert track.track.number == expected  # TODO: flakey assertion - very rare

    def test_set_value_with_group(
            self, model: IncrementalSetter, tracks: list[Track], tracks_group: list[Track], faker: Faker
    ):
        track = faker.random_element(tracks_group)
        track.track.total = None  # avoid errors with Position validation
        expected = model.start + sorted(tracks_group, key=lambda x: x.artist).index(track) * model.increment

        model.group_by = ["name"]
        model.sort_by = ItemSorter(sort_fields={"artist": False})
        model.set(track, tracks)
        assert track.track.number == expected
