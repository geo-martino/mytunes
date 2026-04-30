from abc import ABCMeta

import pytest
from faker import Faker

from mytunes.core._item.track import Track
from mytunes.exception import MyTunesValueError
from mytunes.processors.sort import ItemSorter
from mytunes.processors.tagger import MaxValue
from mytunes.processors.tagger._setter import ValueSetter, GroupSetter, SortSetter, IncrementalSetter, _GroupSetter
from mytunes.processors.tagger.values import FixedValue
from tests.testers import BaseModelTester


class TestValueSetter(BaseModelTester):
    @pytest.fixture
    def model(self, tracks: list[Track], faker: Faker) -> ValueSetter:
        model = ValueSetter(field="artist", value=FixedValue(name="name", value=faker.name()))
        model.set_context(tracks)
        return model

    def test_set_value(self, model: ValueSetter, track: Track, faker: Faker):
        value = faker.name()
        model.field = "artist"
        model.value = value

        assert track.artist != value
        model.set(track)
        assert track.artist == value

    def test_set_value_for_collection_value(self, model: ValueSetter, tracks: list[Track], faker: Faker):
        expected = max(track.track.number for track in tracks)
        track = faker.random_element(tracks)
        track.track.total = None

        model.field = "track.total"
        model.value = MaxValue(field="track.number")

        model.set(track)
        assert track.track.total == expected


class GroupedSetterTester(BaseModelTester, metaclass=ABCMeta):
    @pytest.fixture
    def tracks_group(self, model: _GroupSetter, tracks: list[Track], faker: Faker) -> list[Track]:
        model.group_by = ["name"]

        tracks = list(faker.random_elements(tracks, unique=True))
        name = faker.sentence()

        for track in tracks:
            track.name = name

        model.set_context(tracks)
        return tracks

    @staticmethod
    def test_gets_item_from_groups(model: _GroupSetter, tracks_group: list[Track], faker: Faker):
        track = faker.random_element(tracks_group)
        assert model._get_group(track) == tuple(tracks_group)

    @staticmethod
    def test_set_fails_when_item_not_in_groups(model: _GroupSetter, tracks: list[Track]):
        model.group_by = ["name"]

        track = tracks.pop(0)
        model.set_context(tracks)

        with pytest.raises(MyTunesValueError):  # FIXME: flakey assertion - very rare
            model.set(track)

    @staticmethod
    def test_set_fails_on_no_groups(model: _GroupSetter, tracks: list[Track], faker: Faker):
        track = faker.random_element(tracks)

        model.clear_context()
        with pytest.raises(MyTunesValueError):
            model.set(track)

    def test_set_value_for_group(self, model: _GroupSetter, tracks_group: list[Track], faker: Faker):
        track = faker.random_element(tracks_group)
        expected = max(track.track.number for track in tracks_group)

        model.set(track)
        assert track.track.total == expected


class TestGroupedSetter(GroupedSetterTester):
    @pytest.fixture
    def model(self, tracks: list[Track], faker: Faker) -> GroupSetter:
        model = GroupSetter(field="track.total", value=MaxValue(field="track.number"))
        model.set_context(tracks)
        return model

    def test_set_value(self, model: GroupSetter, tracks: list[Track], faker: Faker):
        track = faker.random_element(tracks)
        expected = max(track.track.number for track in tracks)

        model.set(track)
        assert track.track.total == expected


class TestSortedSetter(GroupedSetterTester):
    @pytest.fixture
    def model(self, tracks: list[Track], faker: Faker) -> SortSetter:
        model = SortSetter(field="track.total", value=MaxValue(field="track.number"))
        model.set_context(tracks)
        return model

    def test_set_value(self, model: SortSetter, tracks: list[Track], faker: Faker):
        track = faker.random_element(tracks)
        expected = max(track.track.number for track in tracks)

        model.set(track)
        assert track.track.total == expected

    def test_set_value_with_sort(self, model: SortSetter, tracks: list[Track], faker: Faker):
        track = faker.random_element(tracks)
        expected = max([track.track.number for track in tracks])

        model.sort_by = ItemSorter(sort_fields={"name": True})
        model.set(track)
        assert track.track.total == expected


class TestIncrementalSetter(GroupedSetterTester):
    @pytest.fixture
    def model(self, tracks: list[Track], faker: Faker) -> IncrementalSetter:
        start = faker.random_int(1, 10)
        increment = faker.random_int(1, 10)

        model = IncrementalSetter(field="track.number", start=start, increment=increment)
        model.set_context(tracks)
        return model

    def test_set_value(self, model: IncrementalSetter, tracks: list[Track], faker: Faker):
        track = faker.random_element(tracks)
        track.track.total = None  # avoid errors with Position validation
        expected = model.start + tracks.index(track) * model.increment

        model.set(track)
        assert track.track.number == expected

    def test_set_value_with_sort(self, model: IncrementalSetter, tracks: list[Track], faker: Faker):
        track = faker.random_element(tracks)
        track.track.total = None  # avoid errors with Position validation
        expected = model.start + sorted(tracks, key=lambda x: x.name, reverse=True).index(track) * model.increment

        model.sort_by = ItemSorter(sort_fields={"name": True})
        model.set(track)
        assert track.track.number == expected  # FIXME: flakey assertion - very rare

    def test_set_value_for_group(self, model: IncrementalSetter, tracks_group: list[Track], faker: Faker):
        track = faker.random_element(tracks_group)
        track.track.total = None  # avoid errors with Position validation
        expected = model.start + sorted(tracks_group, key=lambda x: x.artist).index(track) * model.increment

        model.group_by = ["name"]
        model.sort_by = ItemSorter(sort_fields={"artist": False})
        model.set(track)
        assert track.track.number == expected
