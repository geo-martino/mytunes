from pathlib import Path

import pytest
from faker import Faker
from mytunes._models.item.track import Track
from mytunes._models.properties.file import IsLocalFile
from mytunes._models.properties.order import Position
from mytunes.processors.filters.values import ValueFilter
from mytunes.processors.tagger.values._fields import FieldValue, PositionValue, PathValue
from tests.testers import BaseModelTester


class TestFieldValue(BaseModelTester):
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

    def test_applies_filter(self, track: Track, faker: Faker):
        track.artist = faker.name()
        condition = ValueFilter(values={track.name})
        assert not condition.check(track.artist)

        model = FieldValue(field="artist", condition=condition)
        assert model.get(track) is None


class TestPositionValue(BaseModelTester):
    @pytest.fixture
    def model(self) -> PositionValue:
        return PositionValue(field="track")

    @pytest.fixture
    def position(self, faker: Faker) -> Position:
        return Position(number=faker.random_int(1, 20), total=faker.random_int(100, 500))

    def test_get_value(self, track: Track, position: Position):
        track.track = position
        model = PositionValue(field="track")
        assert model.get(track) == position

    def test_get_value_with_zero_fill(self, track: Track, position: Position, faker: Faker):
        leading_zeros = faker.random_element((faker.boolean(), faker.random_int(0, 100)))
        track.disc = position

        model = PositionValue(field="disc", leading_zeros=leading_zeros)
        assert model.get(track).zero_fill == leading_zeros

    def test_get_missing_value(self, track: Track):
        assert track.disc is None
        model = PositionValue(field="disc")
        assert model.get(track) is None

    def test_applies_filter(self, track: Track, position: Position):
        track.disc = position
        condition = ValueFilter(values={track.name})
        assert not condition.check(track.disc)

        model = PositionValue(field="disc", condition=condition)
        assert model.get(track) is None


class TestPathValue(BaseModelTester):
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
        assert model.get(file) == path

    def test_get_value_with_parent(self, file: IsLocalFile, path: Path):
        file.path = Path("./path/to/a/file.txt")

        model = PathValue(field="path", parent=2)
        assert model.get(file) == "to"

        model = PathValue(field="path", parent=3)
        assert model.get(file) == "path"

    def test_applies_filter(self, file: IsLocalFile, path: Path, faker: Faker):
        file.path = path
        condition = ValueFilter(values={faker.word()})
        assert not condition.check(file.path)

        model = PathValue(field="path", condition=condition)
        assert model.get(file) is None
