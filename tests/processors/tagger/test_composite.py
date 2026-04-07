import pytest
from faker import Faker

from musify._models.item.track import Track
from musify.exception import MusifyValueError
from musify.processors.tagger._composite import TemplateValue, JoinValue
from musify.processors.tagger._value import FieldValue, PathValue, FixedValue
from tests.testers import BaseModelTester


class TestJoinValue(BaseModelTester):
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

        model = JoinValue(fields=["name", "key"])
        with pytest.raises(MusifyValueError):
            model.get(track)


class TestTemplateValue(BaseModelTester):
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

        model = TemplateValue(template="{name} {sep} {artist}", fields=[FixedValue(field="sep", value="-")])
        assert model.get(track) == expected

    def test_get_value_fails_on_missing(self, track: Track, faker: Faker):
        assert track.key is None

        model = TemplateValue(template="{name} - {key}")
        with pytest.raises(MusifyValueError):
            model.get(track)
