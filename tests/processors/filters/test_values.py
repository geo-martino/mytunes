from copy import deepcopy
from pathlib import Path
from random import shuffle, choice

import pytest
from faker import Faker

from musify.models.properties.file import IsLocalFile
from musify.processors.filters.values import ValuesFilter, PathsFilter
from tests.processors.filters.testers import FilterTester


class TestValuesFilter(FilterTester):

    @pytest.fixture
    def model(self, faker: Faker) -> ValuesFilter:
        values = {faker.pystr(30, 50) for _ in range(20)}
        return ValuesFilter(values=values)

    def test_from_values(self, faker: Faker):
        values = faker.words()
        assert ValuesFilter.model_validate(values) == ValuesFilter(values=set(values))

    def test_equality(self, model: ValuesFilter, faker: Faker):
        assert model == deepcopy(model)

        new_filter = model.__class__(values=deepcopy(model.values))
        assert model == new_filter

        new_filter.values = set(deepcopy(list(model.values)[len(model.values) // 2]))
        assert model != new_filter

    def test_check(self, model: ValuesFilter, faker: Faker):
        values = list(model.values)
        assert all(model.check(value) for value in values)

        values_missing = {faker.pystr(30, 50) for _ in range(10)} - model.values
        assert not any(model.check(value) for value in values_missing)

    def test_apply_on_empty_filter(self, model: ValuesFilter):
        assert model.__class__().apply(model.values) == list(model.values)

    def test_apply(self, model: ValuesFilter):
        values = list(model.values)
        expected = values.copy()
        shuffle(expected)

        filter_ = ValuesFilter(values=model.values)
        assert filter_.apply(values[:10]) == values[:10]


class TestPathsFilter(TestValuesFilter):

    @pytest.fixture
    def model(self, faker: Faker) -> PathsFilter:
        values = {faker.file_path() for _ in range(20)}
        return PathsFilter(values=values)

    def test_extract_values(self, model: PathsFilter, faker: Faker):
        expected = [faker.file_path() for _ in range(10)]
        values = [choice([value, Path(value), IsLocalFile(path=Path(value))]) for value in expected]
        # noinspection PyTypeChecker
        assert PathsFilter(values=values).values == set(expected)
