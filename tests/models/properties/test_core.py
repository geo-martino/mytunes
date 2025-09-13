from random import choice

import pytest
from faker import Faker

from musify.models import MusifyModel
from musify.models.properties import HasSeparableTags
from tests.models.testers import MusifyResourceTester


class TestHasSeparableTags(MusifyResourceTester):
    @pytest.fixture
    def model(self) -> MusifyModel:
        return HasSeparableTags()

    def test_join_tags(self, faker: Faker) -> None:
        tags = faker.words(nb=faker.random_int(10, 20))

        HasSeparableTags._tag_sep = ("/", ";")
        assert HasSeparableTags._join_tags(tags) == "/".join(tags), "Should only join on first item in the sequence"

    def test_separate_tags(self, faker: Faker) -> None:
        tags = faker.words(nb=faker.random_int(10, 20))

        seps = ("/", ";")
        HasSeparableTags._tag_sep = ("/", ";")
        tags_joined = "".join(tag + choice(seps) for tag in tags)
        assert HasSeparableTags._separate_tags(tags_joined) == tags
