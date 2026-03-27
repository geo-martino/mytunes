import random
from collections.abc import Generator
from typing import get_args
from unittest.mock import patch, Mock

import pytest
from faker import Faker
from pydantic import ValidationError
from pytest_mock import MockerFixture

from musify import MODULE_ROOT
from musify.models.item.artist import Artist, HasArtists
from musify.models.item.track import Track, HasTracks
from musify.models.properties.order import Position
from musify.processors_new.formatter import ModelFormatter, FIELDS, COLOURS, COLOUR_ATTRIBUTES, CollectionFormatter
from tests.models.testers import BaseModelTester


class TestModelFormatter(BaseModelTester):
    @pytest.fixture
    def model(self) -> ModelFormatter:
        return ModelFormatter(
            fields=get_args(FIELDS),
        )

    @pytest.fixture
    def tracks(self, tracks: list[Track], faker: Faker) -> list[Track]:
        for track in tracks:
            track.length = faker.random_int(min=1, max=100) if faker.boolean() else None
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
        alignment = faker.random_element(("left", "right", "center", "decimal"))
        formatter = ModelFormatter(fields=fields, alignments=alignment)
        assert formatter.alignments == [alignment] * len(fields), "Alignment should be applied to all fields"

    def test_validate_alignments_match_fields(self, faker: Faker):
        fields = get_args(FIELDS)
        supported_alignments = ("left", "right", "center", "decimal")
        log = "The number of alignments must match the number of fields"

        too_few_alignments = [
            faker.random_element(supported_alignments)
            for _ in range(len(fields) - faker.random_int(1, len(fields) - 2))
        ]
        with pytest.raises(ValidationError, match=log):
            ModelFormatter(fields=fields, alignments=too_few_alignments)

        too_many_alignments = [
            faker.random_element(supported_alignments)
            for _ in range(len(fields) + faker.random_int(2, len(fields) - 1))
        ]
        with pytest.raises(ValidationError, match=log):
            ModelFormatter(fields=fields, alignments=too_many_alignments)

        # this is fine
        valid_alignments = [faker.random_element(supported_alignments) for _ in range(len(fields))]
        ModelFormatter(fields=fields, alignments=valid_alignments)

    @pytest.fixture
    def mock_tabulate(self) -> Generator[Mock, None, None]:
        with patch(f"{MODULE_ROOT}.processors_new.formatter.tabulate") as mock_tabulate:
            yield mock_tabulate

    @pytest.fixture
    def values(self, model: ModelFormatter, tracks: list[Track]) -> list[tuple[str, ...]]:
        def _get_value(track: Track, field: str):
            value = getattr(track, field.lower().replace(" ", "_"), None)
            return value if value is not None else ""

        return [tuple(_get_value(track, field) for field in model.fields) for track in tracks]

    def test_extract_values(
            self,
            model: ModelFormatter,
            tracks: list[Track],
            values: list[tuple[str, ...]],
            mock_tabulate: Mock,
            faker: Faker,
    ):
        model.format(tracks)
        mock_tabulate.assert_called_once()

        rows = mock_tabulate.call_args.args[0]
        assert rows == values

    def test_uses_default_kwargs(
            self,
            model: ModelFormatter,
            tracks: list[Track],
            mock_tabulate: Mock,
            faker: Faker,
    ):
        model.header = True
        model.alignments = [faker.random_element(("left", "right", "center", "decimal")) for _ in model.fields]
        model.widths = [faker.random_int() for _ in model.fields]
        model.missing_value = faker.word()

        model.format(tracks, indices=False)
        mock_tabulate.assert_called_once()

        kwargs = mock_tabulate.call_args.kwargs
        assert kwargs["headers"] == model.fields
        assert kwargs["colalign"] == model.alignments
        assert kwargs["maxcolwidths"] == model.widths
        assert kwargs["missingval"] == model.missing_value
        assert kwargs["showindex"] is False

    def test_adds_index(
            self,
            model: ModelFormatter,
            tracks: list[Track],
            values: list[tuple[str, ...]],
            mock_tabulate: Mock,
            faker: Faker,
    ):
        indices = list(range(1, len(tracks) + 1))
        if faker.boolean():
            indices = list(map(Position.model_validate, indices))

        model.format(tracks, indices=indices)
        mock_tabulate.assert_called_once()

        kwargs = mock_tabulate.call_args.kwargs
        assert kwargs["showindex"] == list(map(str, indices))

    def test_truncates_values(
            self,
            model: ModelFormatter,
            tracks: list[Track],
            values: list[tuple[str, ...]],
            mock_tabulate: Mock,
            faker: Faker,
    ):
        model.widths = 5
        model.truncate = True
        assert any(len(str(val)) > model.widths[0] for row in values for val in row)  # will truncate some values

        model.format(tracks)
        mock_tabulate.assert_called_once()

        rows = mock_tabulate.call_args.args[0]
        assert rows != values

        for row, row_original in zip(rows, values):
            for value, original, width in zip(row, row_original, model.widths):
                assert len(str(value)) <= width, "Value should be truncated to the specified width"
                if len(str(original)) > width:
                    assert str(value).endswith("..."), "Truncated value should end with '...'"

    def test_colours_values(
            self,
            model: ModelFormatter,
            tracks: list[Track],
            values: list[tuple[str, ...]],
            mock_tabulate: Mock,
            faker: Faker,
    ):
        model.colours = [faker.random_element(get_args(COLOURS)) for _ in model.fields]
        model.colour_attributes = [faker.random_element(get_args(COLOUR_ATTRIBUTES)) for _ in model.fields]

        def _to_str(v, *_, **__) -> str:
            return str(v)

        with patch(f"{MODULE_ROOT}.processors_new.formatter.colored", side_effect=_to_str) as mock_colored:
            model.format(tracks)

            rows = mock_tabulate.call_args.args[0]
            for row in rows:
                for value, colour, attributes in zip(row, model.colours, model.colour_attributes):
                    if value is None or value == "":
                        continue
                    mock_colored.assert_any_call(value, color=colour, attrs=attributes)

    def test_full_format(
            self, model: ModelFormatter, tracks: list[Track], faker: Faker,
    ):
        model.header = True
        model.alignments = [faker.random_element(("left", "right", "center", "decimal")) for _ in model.fields]
        model.widths = [faker.random_int() for _ in model.fields]
        model.missing_value = faker.word()

        indices = list(range(1, len(tracks) + 1))
        if faker.boolean():
            indices = [Position(number=i, total=len(tracks), zero_fill=True) for i in indices]

        result = model.format(tracks, indices=indices)
        assert isinstance(result, str)
        assert len(result.splitlines()) > len(tracks)  # should have header row


class TestCollectionFormatter(BaseModelTester):
    @pytest.fixture
    def model(self) -> CollectionFormatter:
        return CollectionFormatter(
            fields=get_args(FIELDS),
        )

    def test_format_uses_current_positions(
            self, model: CollectionFormatter, tracks: list[Track], mocker: MockerFixture, faker: Faker
    ):
        collection = HasTracks(tracks=tracks)
        total = len(tracks)

        random.shuffle(tracks)
        for i, track in enumerate(tracks, 1):
            track.track = Position(number=i, total=total)

        mock_format = mocker.spy(ModelFormatter, "format")

        model.format(collection, indices=True)

        mock_format.assert_called_once()
        # different order expected
        kwargs = mock_format.call_args.kwargs
        assert kwargs["indices"] == [track.track for track in collection.items]
        assert kwargs["indices"] != [track.track for track in tracks]

    def test_format_generates_positions(
            self, model: CollectionFormatter, artists: list[Artist], mocker: MockerFixture, faker: Faker
    ):
        collection = HasArtists(artists=artists)
        expected = [Position(number=i, total=len(artists), zero_fill=True) for i in range(1, len(artists) + 1)]

        mock_format = mocker.spy(ModelFormatter, "format")

        model.format(collection, indices=True)

        mock_format.assert_called_once()
        kwargs = mock_format.call_args.kwargs
        assert kwargs["indices"] == expected
