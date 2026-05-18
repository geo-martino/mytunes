import random
from typing import get_args
from unittest.mock import Mock

import pytest
from faker import Faker
from pydantic import ValidationError
from pytest_mock import MockerFixture
from rich.table import Table, Column

from mytunes.core._item.artist import Artist
from mytunes.core._item.track import Track
from mytunes.core.properties.length import Length
from mytunes.core.properties.order import Position
from mytunes.processors.formatter import ModelFormatter, CollectionFormatter, FIELDS, ALIGNMENTS
from tests.processors.utils import MockCollection
from tests.testers import BaseModelTester


class TestModelFormatter(BaseModelTester):
    @pytest.fixture
    def model(self) -> ModelFormatter:
        return ModelFormatter(
            fields=get_args(FIELDS),
        )

    @pytest.fixture
    def tracks(self, tracks: list[Track], faker: Faker) -> list[Track]:
        for track in tracks:
            track.__dict__["length"] = Length(root=faker.random_int(min=1, max=100)) if faker.boolean() else None
        return tracks

    def test_applies_width_to_all_fields(self, faker: Faker):
        fields = get_args(FIELDS)
        width = faker.random_int(min=1, max=100)
        formatter = ModelFormatter(fields=fields, widths=width)
        assert formatter.widths == [width] * len(fields), "Width should be applied to all fields"

    def test_validate_widths_match_fields(self, faker: Faker):
        fields = get_args(FIELDS)
        log = "The number of widths must match the number of fields"

        too_few_widths = [
            faker.random_int(min=1, max=100)
            for _ in range(len(fields) - faker.random_int(1, len(fields) - 2))
        ]
        with pytest.raises(ValidationError, match=log):
            ModelFormatter(fields=fields, widths=too_few_widths)

        too_many_widths = [
            faker.random_int(min=1, max=100)
            for _ in range(len(fields) + faker.random_int(2, len(fields) - 1))
        ]
        with pytest.raises(ValidationError, match=log):
            ModelFormatter(fields=fields, widths=too_many_widths)

        # this is fine
        valid_widths = [faker.random_int(min=1, max=100) for _ in range(len(fields))]
        ModelFormatter(fields=fields, widths=valid_widths)

    def test_applies_alignment_to_all_fields(self, faker: Faker):
        fields = get_args(FIELDS)
        alignment = faker.random_element(get_args(ALIGNMENTS))
        formatter = ModelFormatter(fields=fields, alignments=alignment)
        assert formatter.alignments == [alignment] * len(fields), "Alignment should be applied to all fields"

    def test_validate_alignments_match_fields(self, faker: Faker):
        fields = get_args(FIELDS)
        log = "The number of alignments must match the number of fields"

        too_few_alignments = [
            faker.random_element(get_args(ALIGNMENTS))
            for _ in range(len(fields) - faker.random_int(1, len(fields) - 2))
        ]
        with pytest.raises(ValidationError, match=log):
            ModelFormatter(fields=fields, alignments=too_few_alignments)

        too_many_alignments = [
            faker.random_element(get_args(ALIGNMENTS))
            for _ in range(len(fields) + faker.random_int(2, len(fields) - 1))
        ]
        with pytest.raises(ValidationError, match=log):
            ModelFormatter(fields=fields, alignments=too_many_alignments)

        # this is fine
        valid_alignments = [faker.random_element(get_args(ALIGNMENTS)) for _ in range(len(fields))]
        ModelFormatter(fields=fields, alignments=valid_alignments)

    @pytest.fixture
    def values(self, model: ModelFormatter, tracks: list[Track]) -> list[tuple[str, ...]]:
        def _get_value(track: Track, field: str):
            value = getattr(track, field.lower().replace(" ", "_"), None)
            return value if value is not None else ""

        return [tuple(_get_value(track, field) for field in model.fields) for track in tracks]

    @staticmethod
    def assert_table_values(table: Table, values: list[tuple]) -> None:
        assert len(table.rows) == len(values)

        expected_columns = list(map(list, zip(*values)))
        assert len(table.columns) == len(expected_columns)

        for actual, expected in zip(table.columns, expected_columns, strict=True):
            assert list(actual.cells) == expected

    def test_values(self, model: ModelFormatter, tracks: list[Track], values: list[tuple], faker: Faker):
        table = model.format(tracks)
        self.assert_table_values(table, values)

    def test_adds_index(self, model: ModelFormatter, tracks: list[Track], values: list[tuple], faker: Faker):
        indices = list(range(1, len(tracks) + 1))
        if faker.boolean():  # accepts position values too
            indices = list(map(Position.model_validate, indices))

        values = [(str(i), *row) for i, row in zip(indices, values)]

        table = model.format(tracks, indices=indices)
        self.assert_table_values(table, values)

    def test_column_properties(self, model: ModelFormatter, tracks: list[Track], values: list[tuple], faker: Faker):
        model = ModelFormatter(
            fields=model.fields,
            widths=[faker.random_int(min=1, max=100) for _ in range(len(model.fields))],
            alignments=[faker.random_element(get_args(ALIGNMENTS)) for _ in range(len(model.fields))],
            styles=[faker.random_element(("red", "green", "blue", None)) for _ in range(len(model.fields))],
            truncate=[faker.null_boolean() for _ in range(len(model.fields))],
        )

        table = model.format(tracks)

        for actual, name, alignment, width, style, truncate in zip(
            table.columns, model.fields, model.alignments, model.widths, model.styles, model.truncate, strict=True
        ):
            actual: Column
            assert actual.header == name
            assert actual.justify == alignment
            assert actual.width == width
            assert actual.style == (style if style else "")
            assert actual.no_wrap == truncate
            assert actual.overflow == "ellipsis" if truncate else "fold"


class TestCollectionFormatter(BaseModelTester):
    @pytest.fixture
    def model(self) -> CollectionFormatter:
        return CollectionFormatter(
            fields=get_args(FIELDS),
        )

    @pytest.fixture
    def mock_format(self, mocker: MockerFixture) -> Mock:
        return mocker.spy(ModelFormatter, "format")

    def test_format_uses_current_positions(
            self, model: CollectionFormatter, tracks: list[Track], mock_format: Mock, faker: Faker
    ):
        collection = MockCollection(name=faker.name(), all_items=tracks)
        total = len(tracks)

        random.shuffle(tracks)
        for i, track in enumerate(tracks, 1):
            track.track = Position(number=i, total=total)

        model.format(collection, indices=True)

        mock_format.assert_called_once()
        # different order expected
        kwargs = mock_format.call_args.kwargs
        assert kwargs["indices"] == [track.track for track in collection.items]
        assert kwargs["indices"] != [track.track for track in tracks]

    def test_format_generates_positions(
            self, model: CollectionFormatter, artists: list[Artist], mock_format: Mock, faker: Faker
    ):
        collection = MockCollection(name=faker.name(), all_items=artists)
        expected = [Position(number=i, total=len(artists), zero_fill=True) for i in range(1, len(artists) + 1)]

        model.format(collection, indices=True)

        mock_format.assert_called_once()
        kwargs = mock_format.call_args.kwargs
        assert kwargs["indices"] == expected

    def test_format_uses_count_as_total(
            self, model: CollectionFormatter, tracks: list[Track], mock_format: Mock, faker: Faker
    ):
        total = len(tracks)
        random.shuffle(tracks)
        for i, track in enumerate(tracks, 1):
            track.track = Position(number=i, total=None)

        collection = MockCollection(name=faker.name(), all_items=tracks)
        expected = [Position(number=it.track.number, total=total, zero_fill=True) for it in collection.items]

        model.format(collection, indices=True)

        mock_format.assert_called_once()
        kwargs = mock_format.call_args.kwargs
        assert kwargs["indices"] == expected

    def test_format_gets_valid_total_from_invalid_positions(
            self, model: CollectionFormatter, tracks: list[Track], mock_format: Mock, faker: Faker
    ):
        total = len(tracks)
        random.shuffle(tracks)
        for i, track in enumerate(tracks, 1):
            track_total = faker.random_element((None, total, i))
            track.track = Position(number=i, total=track_total)

        if not any(track.track.total == total for track in tracks):
            tracks[-1].track.total = total

        collection_tracks = faker.random_elements(tracks, length=len(tracks) // 3, unique=True)
        collection_tracks = sorted(collection_tracks, key=lambda it: it.track.number)
        collection = MockCollection(name=faker.name(), all_items=collection_tracks)
        expected = [Position(number=it.track.number, total=total, zero_fill=True) for it in collection.items]

        model.format(collection, indices=True)

        mock_format.assert_called_once()
        kwargs = mock_format.call_args.kwargs
        assert kwargs["indices"] == expected
