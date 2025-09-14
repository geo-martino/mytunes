from copy import deepcopy, copy
from datetime import datetime, date, timedelta
from random import choice, sample

import pytest
from faker import Faker

from musify.local.item.track import LocalTrack
from musify.local.item.track.mp3 import MP3
from musify.models.properties.order import Position
from musify.processors_new.compare import Comparer, COMPARISON_FIELDS
from musify.processors_new.exception import ComparerError
from tests.models.testers import MusifyModelTester


class TestComparer(MusifyModelTester):

    @pytest.fixture
    def model(self) -> Comparer:
        return Comparer(condition=" is  _", expected=[".mp3", ".flac"], field="ext")

    @pytest.fixture
    def track(self, faker: Faker) -> MP3:
        """Returns a random MP3 track from the provided tracks."""
        return MP3(
            name=faker.sentence(nb_words=faker.random_int(1, 5)),
            path=faker.file_path(extension=".mp3")
        )

    def test_init_fails(self):
        with pytest.raises(ValueError):
            Comparer(condition="this cond does not exist", field="ext")

    def test_init_1(self):
        comparer = Comparer(condition="Contains", field="comments")
        assert comparer.field == "comments"
        assert comparer.expected is None
        assert comparer.condition == "contains"
        assert comparer._processor_method == comparer._contains

    def test_init_2(self):
        comparer = Comparer(condition="___greater than_  ", field="added_at")
        assert comparer.field == "added_at"
        assert comparer.expected is None
        assert comparer.condition == "greater_than"
        assert comparer._processor_method == comparer._is_after

    def test_init_3(self):
        comparer = Comparer(condition=" is  _", expected=[".mp3", ".flac"], field="ext")
        assert comparer.field == "ext"
        assert comparer.expected == [".mp3", ".flac"]
        assert comparer.condition == "is"
        assert comparer._processor_method == comparer._is

    def test_equality(self, model: Comparer):
        assert model == deepcopy(model)

        new_filter = Comparer(
            condition=model.condition,
            expected=deepcopy(model.expected),
            field=model.field,
            reference_required=model.reference_required
        )
        assert model == new_filter

        while new_filter.field == model.field:
            new_filter.field = choice(list(COMPARISON_FIELDS))
        assert model != new_filter

    def test_compare_on_noexpected_value(self, tracks: list[LocalTrack]):
        track = choice(tracks)
        comparer = Comparer(condition="is null", field="disc_total")
        track.disc = Position(number=4, total=None)

        assert comparer.compare(track)

        comparer = Comparer(condition="is not null", field="disc_total")
        assert not comparer.compare(track)

    def test_compare_with_reference(self, tracks: list[LocalTrack]):
        track_1, track_2 = sample(tracks, 2)

        comparer = Comparer(condition="StartsWith", field="album", reference_required=True)
        assert comparer.expected is None

        with pytest.raises(ComparerError):
            comparer.compare(item=track_1)

        track_1.album = "album 124 is a great album"
        track_2.album = "album"
        assert comparer.compare(item=track_1, reference=track_2)
        assert comparer(item=track_1, reference=track_2)
        assert comparer.expected is None

        with pytest.raises(ComparerError):
            comparer.compare(item=track_1)

    def test_compare_str(self, track: MP3):
        comparer = Comparer(condition=" is  _", expected=".mp3", field="ext")
        assert comparer.expected == ".mp3"
        assert comparer._processor_method == comparer._is

        assert track.ext == ".mp3"
        assert comparer.compare(track)

        comparer.expected = ".txt"
        assert not comparer.compare(track)

    def test_compare_int(self, track: MP3):
        expected = ["1", 2, "3"]
        comparer = Comparer(condition="is in", expected=["1", 2, "3"], field="track")
        assert comparer.expected == [Position(number=num) for num in expected]
        assert comparer._processor_method == comparer._is_in

        track.track = Position(number=3)
        assert comparer.compare(track)

        track.track = Position(number=4)
        assert not comparer.compare(track)

    def test_compare_length(self, track: MP3):
        comparer = Comparer(condition="greater than", expected="1:30,618", field="length")
        assert comparer.expected == 90.618
        assert comparer._processor_method == comparer._is_after

        track.length = 120
        assert comparer.compare(track)

        track.length = 60
        assert not comparer.compare(track)

    def test_compare_float(self, track: MP3):
        comparer = Comparer(condition="in_range", expected=["81.96", 100.23], field="bpm")
        assert comparer.expected == [81.96, 100.23]
        assert comparer._processor_method == comparer._in_range

        track.bpm = 90.0
        assert comparer.compare(track)

        track.bpm = 120
        assert not comparer.compare(track)

    def test_compare_date(self, track: MP3):
        expected = datetime(2023, 4, 21, 19, 20)
        comparer = Comparer(condition="is", expected=expected.isoformat(), field="added_at")
        assert comparer.expected == expected
        assert comparer._processor_method == comparer._is

        track.added_at = copy(expected)
        assert comparer.compare(track)

        track.added_at += timedelta(days=1)
        assert not comparer.compare(track)

    def test_compare_date_ranges(self, track: MP3):
        comparer = Comparer(condition="in_the_last", expected="8h", field="added_at")
        assert comparer.expected == "8h"
        assert comparer._processor_method == comparer._is_after

        track.added_at = datetime.now() - timedelta(hours=4)
        assert comparer.compare(track)
        # truncate to avoid time lag between assignment and test making the test fail
        exp_truncated = comparer.expected[0].replace(second=0, microsecond=0)
        test_truncated = datetime.now().replace(second=0, microsecond=0) - timedelta(hours=8)
        assert exp_truncated == test_truncated
