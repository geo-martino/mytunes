import pytest
from faker import Faker

from musify._models.item.track import Track
from musify._models.properties.order import Position
from musify.processors.tagger._collection import MinValue, MaxValue
from tests.testers import BaseModelTester


class TestMinValue(BaseModelTester):
    @pytest.fixture
    def model(self) -> MinValue:
        return MinValue(field="track.number")

    @pytest.fixture
    def tracks(self, tracks: list[Track], faker: Faker) -> list[Track]:
        total = faker.random_int(50, 100)
        for track in tracks:
            track.track = Position(number=faker.random_int(1, total), total=total)
        return tracks

    def test_get_value(self, tracks: list[Track]):
        model = MinValue(field="track.number")
        assert model.get(tracks) == min(track.track.number for track in tracks)

    def test_get_value_not_fails_on_missing(self, tracks: list[Track], faker: Faker):
        for track in faker.random_elements(tracks, length=faker.random_int(1, len(tracks) - 1), unique=True):
            track.track = None

        model = MinValue(field="track.number")
        assert model.get(tracks) == min(track.track.number for track in tracks if isinstance(track.track, Position))


class TestMaxValue(BaseModelTester):
    @pytest.fixture
    def model(self) -> MaxValue:
        return MaxValue(field="track.number")

    @pytest.fixture
    def tracks(self, tracks: list[Track], faker: Faker) -> list[Track]:
        total = faker.random_int(50, 100)
        for track in tracks:
            track.track = Position(number=faker.random_int(1, total), total=total)
        return tracks

    def test_get_value(self, tracks: list[Track]):
        model = MaxValue(field="track.number")
        assert model.get(tracks) == max(track.track.number for track in tracks)

    def test_get_value_not_fails_on_missing(self, tracks: list[Track], faker: Faker):
        for track in faker.random_elements(tracks, length=faker.random_int(1, len(tracks) - 1), unique=True):
            track.track = None

        model = MaxValue(field="track.number")
        assert model.get(tracks) == max(track.track.number for track in tracks if isinstance(track.track, Position))
