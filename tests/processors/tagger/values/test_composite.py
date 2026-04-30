import pytest
from faker import Faker

from mytunes.core._item.track import Track
from mytunes.core.properties.order import Position
from mytunes.exception import MyTunesValueError
from mytunes.processors.filters import ValueFilter, ComparerFilter
from mytunes.processors.tagger.values import FixedValue
from mytunes.processors.tagger.values._composite import TemplateValue, JoinValue
from mytunes.processors.tagger.values._fields import FieldValue, PathValue
from processors.tagger.values.testers import ValueTester
from tests.testers import BaseModelTester


class TestJoinValue(ValueTester):
    @pytest.fixture
    def model(self) -> JoinValue:
        return JoinValue(fields=["name", "artist"])

    def test_get_value(self, track: Track, faker: Faker):
        track.artist = faker.name()
        expected = f"{track.name} - {track.artist}"

        model = JoinValue(fields=["name", "artist"], separator=" - ")
        assert model.get(track) == expected

    def test_get_value_fails_on_missing(self, track: Track, faker: Faker):
        assert track.key is None

        model = JoinValue(fields=["name", "key"], fail_on_missing=True)
        with pytest.raises(MyTunesValueError):
            model.get(track)

    def test_applies_filter(self, track: Track, condition: ComparerFilter):
        assert not condition.check(track)

        model = JoinValue(fields=["name", "key"], condition=condition)
        assert model.get(track) is None



class TestTemplateValue(ValueTester):
    @pytest.fixture
    def model(self) -> TemplateValue:
        return TemplateValue(template="{name} - {artist}")

    def test_adds_fields(self, track: Track, faker: Faker):
        fields = [FieldValue(field="artist"), PathValue(field="path")]
        model = TemplateValue(template="{name} - {artist}", fields=fields)

        fields = [field.field for field in model.fields]
        assert len(fields) == 3
        assert "name" in fields
        assert "artist" in fields

    def test_get_value(self, track: Track, faker: Faker):
        track.artist = faker.name()
        expected = f"{track.name} - {track.artist}"

        model = TemplateValue(template="{name} {sep} {artist}", fields=[FixedValue(name="sep", value="-")])
        assert model.get(track) == expected

    def test_get_value_for_nested_fields(self, track: Track, faker: Faker):
        track.disc = Position(number=faker.random_int())
        track.track = Position(number=faker.random_int())
        expected = f"{track.disc.number}-{track.track.number} {track.name}"

        model = TemplateValue(
            template="{disc.number}{sep}{track.number} {name}", fields=[FixedValue(name="sep", value="-")]
        )
        assert model.get(track) == expected

    def test_get_value_fails_on_missing(self, track: Track, faker: Faker):
        assert track.key is None

        model = TemplateValue(template="{name} - {key}", fail_on_missing=True)
        with pytest.raises(MyTunesValueError):
            model.get(track)

    def test_applies_filter(self, track: Track, condition: ComparerFilter):
        assert not condition.check(track)

        model = TemplateValue(template="{name} - {key}", condition=condition)
        assert model.get(track) is None
