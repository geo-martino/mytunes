from copy import deepcopy

import pytest
from faker import Faker

from musify.processors.filters.composite import IncludeExcludeFilter
from musify.processors.filters.values import ValueFilter
from tests.processors.filters.testers import FilterTester


class TestIncludeExcludeFilter(FilterTester):

    @pytest.fixture
    def model(self, faker: Faker) -> IncludeExcludeFilter:
        include_values = {faker.pystr(30, 50) for _ in range(20)}
        exclude_values = {faker.pystr(30, 50) for _ in range(20)} - include_values

        return IncludeExcludeFilter(
            include=ValueFilter(values=include_values),
            exclude=ValueFilter(values=set(list(include_values)[:10] + list(exclude_values))),
        )

    def test_equality(self, model: IncludeExcludeFilter, faker: Faker):
        new_filter = IncludeExcludeFilter(include=deepcopy(model.include), exclude=deepcopy(model.exclude))
        assert model == new_filter

        new_filter.include = deepcopy(model.exclude)
        new_filter.exclude = deepcopy(model.include)
        assert model != new_filter

    def test_check(self, model: IncludeExcludeFilter, faker: Faker):
        value = next(value for value in model.include.values if value not in model.exclude.values)
        assert model.check(value)

        value = next(value for value in model.include.values if value in model.exclude.values)
        assert not model.check(value)

        value = next(value for value in model.exclude.values)
        assert not model.check(value)

        model.exclude = ValueFilter()
        value = next(value for value in model.include.values)
        assert model.check(value)

    def test_apply(self, model: IncludeExcludeFilter):
        expected = [value for value in model.include.values if value not in model.exclude.values]
        # there should be some overlap between include and exclude values
        assert expected != model.include.values

        assert model.apply(model.include.values) == expected
        assert not model.apply(model.exclude.values)

