from pathlib import Path

import pytest
from faker import Faker

from mytunes.core._item.track import Track
from mytunes.core.properties.file import IsLocalFile
from mytunes.core.properties.order import Position
from mytunes.processors.filters import ComparerFilter
from mytunes.processors.tagger.values._fields import FieldValue, PositionValue, PathValue
from tests.processors.tagger.values.testers import ValueTester


class TestFieldValue(ValueTester):
    @pytest.fixture
    def model(self) -> FieldValue:
        return FieldValue(field="name")

    def test_get_value_1(self, track: Track):
        expected = track.name
        model = FieldValue(field="name")
        assert model.get(track) == expected

    def test_get_value_2(self, track: Track, faker: Faker):
        expected = faker.name()
        track.artist = expected
        model = FieldValue(field="artist")
        assert model.get(track) == expected

    def test_get_missing_value(self, track: Track):
        assert track.key is None
        model = FieldValue(field="key")
        assert model.get(track) is None

    def test_applies_filter(self, track: Track, condition: ComparerFilter):
        assert not condition.check(track)

        model = FieldValue(field="artist", condition=condition)
        assert model.get(track) is None


class TestPositionValue(ValueTester):
    @pytest.fixture
    def model(self) -> PositionValue:
        return PositionValue(field="track")

    @pytest.fixture
    def position(self, faker: Faker) -> Position:
        return Position(
            number=faker.random_int(1, 20), total=faker.random_int(100, 500), zero_fill=True
        )

    def test_get_value(self, track: Track, position: Position):
        track.track = position
        model = PositionValue(field="track")
        assert model.get(track) == str(position)

    def test_get_value_number(self, track: Track, position: Position, faker: Faker):
        track.disc = position
        track.disc.zero_fill = True

        model = PositionValue(field="disc", number=True, total=False)
        assert model.get(track) == str(position.number).zfill(len(str(position.total)))

    def test_get_value_total(self, track: Track, position: Position, faker: Faker):
        track.disc = position
        track.disc.zero_fill = True

        model = PositionValue(field="disc", number=False, total=True)
        assert model.get(track) == str(position.total)

    def test_get_value_sets_zero_fill(self, track: Track, position: Position, faker: Faker):
        track.disc = position
        zero_fill = faker.random_element((faker.boolean(), faker.random_int(0, 100)))
        expected = str(position.model_copy(update={"zero_fill": zero_fill}))

        model = PositionValue(field="disc", zero_fill=zero_fill)
        assert model.get(track) == expected

    def test_get_missing_value(self, track: Track):
        assert track.disc is None
        model = PositionValue(field="disc")
        assert model.get(track) is None

    def test_applies_filter(self, track: Track, position: Position, condition: ComparerFilter):
        assert not condition.check(track)

        model = PositionValue(field="disc", condition=condition)
        assert model.get(track) is None


class TestPathValue(ValueTester):
    @pytest.fixture
    def model(self) -> PathValue:
        return PathValue(field="path")

    @pytest.fixture
    def file(self, path: Path) -> IsLocalFile:
        return IsLocalFile(path=path)

    @pytest.fixture
    def path(self, faker: Faker) -> Path:
        return Path(faker.file_path(depth=faker.random_int(10, 20)))

    def test_get_value(self, file: IsLocalFile, path: Path):
        model = PathValue(field="path")
        assert model.get(file) == str(path)

    def test_get_value_with_parent(self, file: IsLocalFile, path: Path):
        file.path = Path("./path/to/a/file.txt")

        model = PathValue(field="path", parent=2)
        assert model.get(file) == "to"

        model = PathValue(field="path", parent=3)
        assert model.get(file) == "path"

    def test_applies_filter(self, file: IsLocalFile, path: Path, condition: ComparerFilter):
        condition.comparers[0].field = "filename"
        assert not condition.check(file)

        model = PathValue(field="path", condition=condition)
        assert model.get(file) is None
