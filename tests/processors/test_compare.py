import re
from copy import copy
from datetime import datetime, date, timedelta
from random import sample

import pytest
from faker import Faker
from pydantic import ValidationError

from musify._models.properties.date import SparseDate
from musify._models.properties.length import Length
from musify._models.properties.music import KeySignature
from musify._models.properties.order import Position
from musify.exception import MusifyTypeError
from musify.local._item.track import LocalTrack
from musify.local._item.track.mp3 import MP3
from musify.processors.compare import Comparer, _ATTRIBUTE_FIELD_MAP
from musify.processors.time import TimeMapper
from tests.testers import BaseModelTester


class TestComparer(BaseModelTester):

    @pytest.fixture
    def model(self) -> Comparer:
        return Comparer(condition=" is  _", expected=[".mp3", ".flac"], field="ext")

    @pytest.fixture
    def track(self, faker: Faker) -> MP3:
        """Returns a random MP3 track from the provided tracks."""
        return MP3(
            name=faker.sentence(nb_words=faker.random_int(1, 5)),
            path=faker.file_path(extension="mp3")
        )

    def test_init_fails(self):
        with pytest.raises(ValidationError):
            Comparer(condition="this cond does not exist", field="ext")

        with pytest.raises(ValidationError):
            Comparer(condition="Contains", field="track_total")

        with pytest.raises(ValidationError):
            Comparer(condition="Contains", field="album_name")

    def test_init_simple(self):
        comparer = Comparer(condition="Contains", field="comments")
        assert comparer.field == "comments"
        assert comparer.expected is None
        assert comparer.condition == "contains"
        assert comparer._processor_method == comparer._contains

    def test_validates_condition(self):
        comparer = Comparer(condition="___greater than_  ")
        assert comparer.condition == "greater_than"
        assert comparer._processor_method == comparer._is_after

    def test_clears_cache(self, model: Comparer):
        model.condition = "is_not_null"
        # these properties are cached
        assert model._processor_name == "is_not_null"
        assert model._processor_method == model._is_not_null
        assert model._expected_args == ["self", "actual"]

        model.condition = "in_range"
        # cache should clear on changing condition
        assert model._processor_name == "in_range"
        assert model._processor_method == model._in_range
        assert model._expected_args == ["self", "actual", "expected"]

    def test_equality(self, model: Comparer, faker: Faker):
        assert model == copy(model)

        new_filter = Comparer(
            condition=model.condition,
            expected=copy(model.expected),
            field=model.field,
            reference_required=model.reference_required
        )
        assert model == new_filter

        while new_filter.field == model.field:
            new_filter.field = faker.random_element(_ATTRIBUTE_FIELD_MAP.keys())
        assert model != new_filter

    def test_convert_expected_to_none(self):
        comparer = Comparer(condition="is", expected=None, field="disc.total")
        assert comparer.expected is None

        comparer = Comparer(condition="is_null", expected="drop me", field="artist")
        assert comparer.expected is None

        comparer = Comparer(condition="is_not_null", expected="drop me", field="album")
        assert comparer.expected is None

    def test_convert_expected_to_bool(self):
        comparer = Comparer(condition="is", expected="true", field="compilation")
        assert comparer.expected is True
        comparer = Comparer(condition="is_not", expected=0, field="compilation")
        assert comparer.expected is False

    def test_convert_expected_to_str(self):
        comparer = Comparer(condition="is", expected="track name", field="name")
        assert comparer.expected == "track name"
        comparer = Comparer(condition="is_not", expected="track title", field="name")
        assert comparer.expected == "track title"

        comparer = Comparer(condition="starts_with", expected=123, field="name")
        assert comparer.expected == "123"
        comparer = Comparer(condition="ends_with", expected=123.12, field="name")
        assert comparer.expected == "123.12"

        comparer = Comparer(condition="contains", expected=date(2024, 1, 2), field="filename")
        assert comparer.expected == "2024-01-02"
        comparer = Comparer(condition="does_not_contain", expected=datetime(2024, 1, 2), field="ext")
        assert comparer.expected == "2024-01-02 00:00:00"

    def test_convert_expected_to_pattern(self):
        comparer = Comparer(condition="matches_reg_ex", expected=r"\d+", field="released_at")
        assert comparer.expected == re.compile(r"\d+")
        comparer = Comparer(condition="matches_reg_ex_ignore_case", expected=r"\w+", field="folder")
        assert comparer.expected == re.compile(r"\w+")

    def test_convert_expected_to_int(self):
        comparer = Comparer(condition="is", expected=123, field="track.number")
        assert comparer.expected == 123
        comparer = Comparer(condition="is_not", expected=123.12, field="track.total")
        assert comparer.expected == 123

        comparer = Comparer(condition="is_after", expected="123", field="disc.number")
        assert comparer.expected == 123
        comparer = Comparer(condition="is_before", expected="123.0", field="disc.total")
        assert comparer.expected == 123

    def test_convert_expected_to_float(self):
        comparer = Comparer(condition="is", expected=123, field="rating")
        assert comparer.expected == 123.0
        comparer = Comparer(condition="is_not", expected=123.12, field="bpm")
        assert comparer.expected == 123.12

        comparer = Comparer(condition="is_after", expected="123", field="rating")
        assert comparer.expected == 123.0
        comparer = Comparer(condition="is_before", expected="123.12", field="bpm")
        assert comparer.expected == 123.12

    def test_convert_expected_to_length(self):
        comparer = Comparer(condition="is", expected=123, field="length")
        assert comparer.expected == Length.model_validate(123)

    def test_convert_expected_to_date(self):
        comparer = Comparer(condition="is", expected="2024-01", field="released_at")
        assert comparer.expected == SparseDate(year=2024, month=1)

    def test_convert_expected_to_datetime(self):
        comparer = Comparer(condition="is", expected="2024-01-04", field="added_at")
        assert comparer.expected == datetime(2024, 1, 4)
        comparer = Comparer(condition="is_after", expected="2024-02-05 12:34:56", field="modified_at")
        assert comparer.expected == datetime(2024, 2, 5, 12, 34, 56)
        comparer = Comparer(condition="is_before", expected="2024-03-06 10:11:12", field="modified_at")
        assert comparer.expected == datetime(2024, 3, 6, 10, 11, 12)

    def test_convert_expected_to_time_mapper(self):
        comparer = Comparer(condition="is_after", expected="4h", field="added_at")
        assert comparer.expected == TimeMapper(unit="hours", amount=4, add=False)
        comparer = Comparer(condition="is_before", expected="+5d", field="modified_at")
        assert comparer.expected == TimeMapper(unit="days", amount=5, add=True)

    def test_convert_expected_skips_time_mapper(self):
        comparer = Comparer(condition="ends_with", expected="4h", field="name")
        assert comparer.expected == "4h"

        comparer = Comparer(condition="starts_with", expected="1950s", field="album")
        assert comparer.expected == "1950s"
        assert not isinstance(comparer.expected, TimeMapper)

    def test_convert_expected_to_position(self):
        comparer = Comparer(condition="is", expected="1", field="track")
        assert comparer.expected == Position(number=1)
        comparer = Comparer(condition="is_not", expected="1/2", field="disc")
        assert comparer.expected == Position(number=1, total=2)

    def test_convert_expected_to_key(self):
        comparer = Comparer(condition="is", expected="C#m", field="key")
        assert comparer.expected == KeySignature.model_validate("C#m")

    def test_convert_expected_to_set(self):
        comparer = Comparer(condition="is_in", expected=["a", "b", "c"], field="name")
        assert comparer.expected == {"a", "b", "c"}
        comparer = Comparer(condition="is_not_in", expected=(1, 2, 3), field="track.number")
        assert comparer.expected == {1, 2, 3}

    def test_convert_expected_to_tuple(self):
        comparer = Comparer(condition="in_range", expected=["10", "20"], field="track.number")
        assert comparer.expected == (10, 20)
        comparer = Comparer(condition="not_in_range", expected=[1, 10], field="track.total")
        assert comparer.expected == (1, 10)

    def test_convert_expected_skips_sequences(self):
        comparer = Comparer(condition="is_in", expected="album 1", field="album")
        assert comparer.expected == {"album 1"}
        comparer = Comparer(condition="is_in", expected="album 1", field="album")
        assert comparer.expected == {"album 1"}

    def test_compare_with_no_expected_and_no_reference_fails(self, track: MP3, tracks: list[LocalTrack]):
        comparer = Comparer(condition="is", field="name")
        with pytest.raises(MusifyTypeError):
            comparer.compare(track)

    def test_compare_when_reference_required_but_not_provided_fails(self, track: MP3):
        comparer = Comparer(condition="StartsWith", field="album", reference_required=True)
        with pytest.raises(MusifyTypeError):
            comparer.compare(item=track)

    def test_compare_on_null_check(self, track: MP3):
        # no expected value and no reference needed for null checks
        track.disc = Position(number=4, total=None)

        comparer = Comparer(condition="is null", field="disc.total")
        assert comparer.compare(track)

        comparer.condition = "is not null"
        assert not comparer.compare(track)

    def test_compare_with_expected(self, track: MP3):
        track.name = "track name"

        comparer = Comparer(condition="is", expected="track name", field="name")
        assert comparer.compare(track)

        comparer.condition = "is not"
        assert not comparer.compare(track)

    def test_compare_with_reference(self, tracks: list[LocalTrack]):
        track, reference = sample(tracks, 2)
        comparer = Comparer(condition="StartsWith", field="album", reference_required=True)

        track.album = "album 124 is a great album"
        reference.album = "album"
        assert comparer.compare(item=track, reference=reference)

    def test_compare_with_time_mapper(self, track: MP3):
        track.added_at = datetime.now() - timedelta(days=3)

        comparer = Comparer(condition="is after", expected="5d", field="added_at")
        assert comparer.compare(track)

        comparer.expected = "2d"
        assert not comparer.compare(track)
