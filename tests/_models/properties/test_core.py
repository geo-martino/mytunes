from random import choice

import pytest
from faker import Faker

from musify._models.properties import NumberModel
from musify._models.properties.tag import HasSeparableTags
from tests.testers import BaseModelTester


class TestNumberModel(BaseModelTester):
    @pytest.fixture
    def model(self) -> NumberModel:
        return NumberModel(123.45)

    def test_to_number(self, model: NumberModel):
        model.root = 123.45
        assert int(model) == 123

        model.root = 123
        assert float(model) == 123.0

    def test_ordering(self, model: NumberModel):
        assert model == model.root
        assert model < model.root + 2
        assert model > model.root - 2


class TestHasSeparableTags(BaseModelTester):
    @pytest.fixture
    def model(self) -> HasSeparableTags:
        return HasSeparableTags()

    def test_join_tags(self, faker: Faker):
        tags = faker.words(nb=faker.random_int(10, 20))

        HasSeparableTags._tag_sep = ("/", ";")
        assert HasSeparableTags._join_tags(tags) == "/".join(tags), "Should only join on first item in the sequence"

    def test_separate_tags(self, faker: Faker):
        tags = faker.words(nb=faker.random_int(10, 20))

        seps = ("/", ";")
        HasSeparableTags._tag_sep = ("/", ";")
        tags_joined = "".join(tag + choice(seps) for tag in tags)
        assert HasSeparableTags._separate_tags(tags_joined) == tags
