import pytest
from faker import Faker

from mytunes._models.item.track import Track
from mytunes.processors.tagger import Tagger, ValueSetter
from mytunes.processors.tagger.values import FixedValue
from tests.testers import BaseModelTester


class TestTagger(BaseModelTester):
    @pytest.fixture
    def model(self, faker: Faker) -> Tagger:
        setters = [
            ValueSetter(field="name", value=FixedValue(name=faker.word(), value=faker.name()))
        ]
        return Tagger(setters=setters)

    def test_set_tags(self, model: Tagger, tracks: list[Track], faker: Faker):
        value = faker.sentence()
        model.setters = [
            ValueSetter(field="name", value=FixedValue(name=faker.word(), value=value))
        ]

        results = model.set_tags_to_items(tracks)

        assert all(track.name == value for track in tracks)
        assert len(results) == len(tracks)
        assert all(result.fields == ("name",) for result in results.values())
