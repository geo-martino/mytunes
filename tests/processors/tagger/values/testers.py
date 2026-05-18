from abc import ABCMeta

import pytest
from faker import Faker

from mytunes.core.track import Track
from mytunes.processors.compare import Comparer
from mytunes.processors.filters import ComparerFilter
from tests.testers import BaseModelTester


class ValueTester(BaseModelTester, metaclass=ABCMeta):
    @pytest.fixture
    def condition(self, track: Track, faker: Faker) -> ComparerFilter:
        comparer = Comparer(condition="is in", expected=faker.words(), field="name")
        return ComparerFilter(comparers=[comparer])
